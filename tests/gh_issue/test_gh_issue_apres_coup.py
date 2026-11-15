"""
Tests de tools/gh_issue.py : fermeture après coup (close-feature --after-merge), detach-sub-issue et statut d'une idée
(idées #430, #406, #423). Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest
from pathlib import Path

import roadmap_model as rm
from test_gh_issue import Base, NAME


class FermetureApresCoup(Base):
    def setUp(self):
        super().setUp()
        self.texte = Path(self.tmp.name) / "couvre.md"
        self.texte.write_text("Couvre les branches déjà fusionnées : feat/a, feat/b ; idées #12 et #13.", encoding="utf-8")

    def comments(self):
        return self.load()["comments"]

    def test_commentaire_fourni_sans_la_phrase_before_the_merge(self):
        self.add_feature(1, status="In progress")
        code, out, err = self.run_cli("close-feature", "R-1", "--after-merge", "--comment-file", str(self.texte))
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: closed R-1", out)
        cs = self.comments()
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0]["body"], "<!-- roadmap-close -->\nCouvre les branches déjà fusionnées : feat/a, feat/b ; idées #12 et #13.")
        self.assertNotIn("before the merge", cs[0]["body"])
        self.assertNotIn("finish_branch", cs[0]["body"])

    def test_status_done_done_on_et_fermeture_gardes(self):
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1", "--after-merge", "--comment-file", str(self.texte))
        self.assertEqual(self.status_of("R-1"), "Done")
        self.assertEqual(self.issue("R-1")["state"], "closed")
        self.assertEqual(self.issue("R-1")["state_reason"], "completed")
        self.assertEqual(rm.parse_block(self.issue("R-1")["body"])["done_on"], "2026-10-12")

    def test_tete_detachee_sans_phrase_non_plus(self):
        self.head = (None, "abc1234")
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1", "--after-merge", "--comment-file", str(self.texte))
        self.assertNotIn("detached", self.comments()[0]["body"])

    def test_sans_l_option_comportement_inchange(self):
        self.add_feature(1, status="In progress")
        code, _, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.comments()[0]["body"], "<!-- roadmap-close -->\nClosed on branch chore/r65-fixes, before the merge; "
                                                    "the user merges with bash tools/finish_train.sh.")

    def test_rejeu_ne_double_pas_le_commentaire(self):
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1", "--after-merge", "--comment-file", str(self.texte))
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("close-feature", "R-1", "--after-merge", "--comment-file", str(self.texte))
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.comments()), 1)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_usage_les_deux_options_vont_ensemble(self):
        self.add_feature(1, status="In progress")
        self.assertEqual(self.run_cli("close-feature", "R-1", "--after-merge")[0], 2)
        self.assertEqual(self.run_cli("close-feature", "R-1", "--comment-file", str(self.texte))[0], 2)
        self.assertEqual(self.run_cli("close-feature", "R-1", "--after-merge", "--comment-file", str(self.texte.with_name("absent.md")))[0], 2)
        self.texte.write_text("  \n", encoding="utf-8")
        self.assertEqual(self.run_cli("close-feature", "R-1", "--after-merge", "--comment-file", str(self.texte))[0], 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_garde_des_noms_sur_le_texte_fourni(self):
        self.add_feature(1, status="In progress")
        self.texte.write_text(f"Couvre le travail de {NAME}.", encoding="utf-8")
        code, out, err = self.run_cli("close-feature", "R-1", "--after-merge", "--comment-file", str(self.texte))
        self.assertEqual(code, 3)
        self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.issue("R-1")["state"], "open")


class DetacherUneSousIssue(Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1)                                    # issue n°1
        self.idee = self.add_issue("X", "Une idée", ["type:idea"], body="<!-- roadmap-idea: une-idee -->\n\ntexte")      # n°2
        self.autre = self.add_issue("Y", "Une autre", ["type:idea"], body="<!-- roadmap-idea: autre -->\n\ntexte")        # n°3
        self.st = self.load()
        self.st["sub"] = {"1": [2]}
        self.save()
        self.texte = Path(self.tmp.name) / "detache.md"
        self.texte.write_text("Détachée : passe au paquet suivant.", encoding="utf-8")

    def comment_posts(self, n):
        return [c for c in self.calls(writes_only=True) if f"issues/{n}/comments" in " ".join(c["args"])]

    def test_detache_une_sous_issue_presente_par_cle_ou_numero(self):
        code, out, err = self.run_cli("detach-sub-issue", "R-1", "2")
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: detached #2 from #1", out)
        self.assertEqual(self.load()["sub"]["1"], [])
        ecritures = self.calls(writes_only=True)
        self.assertEqual(len(ecritures), 1)
        self.assertIn("DELETE", ecritures[0]["args"])
        self.assertTrue(any(a.endswith("issues/1/sub_issue") for a in ecritures[0]["args"]))
        self.assertEqual(json.loads(ecritures[0]["stdin"]), {"sub_issue_id": 9002})

    def test_numero_avec_diese_pour_les_deux(self):
        self.assertEqual(self.run_cli("detach-sub-issue", "#1", "#2")[0], 0)
        self.assertEqual(self.load()["sub"]["1"], [])

    def test_commentaire_facultatif_sur_l_enfant(self):
        code, _, err = self.run_cli("detach-sub-issue", "R-1", "2", "--comment-file", str(self.texte))
        self.assertEqual(code, 0, err)
        posts = self.comment_posts(2)
        self.assertEqual(len(posts), 1)
        self.assertEqual(json.loads(posts[0]["stdin"]), {"body": "Détachée : passe au paquet suivant."})
        self.assertEqual(self.load()["sub"]["1"], [])

    def test_refus_si_l_enfant_n_est_pas_une_sous_issue_du_parent(self):
        code, _, err = self.run_cli("detach-sub-issue", "R-1", "3", "--comment-file", str(self.texte))
        self.assertEqual(code, 7)
        self.assertIn("not a sub-issue", err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.load()["sub"]["1"], [2])

    def test_refus_d_un_identifiant_inconnu_ou_mal_forme(self):
        self.assertEqual(self.run_cli("detach-sub-issue", "R-1", "99")[0], 7)
        self.assertEqual(self.run_cli("detach-sub-issue", "R-77", "2")[0], 7)
        self.assertEqual(self.run_cli("detach-sub-issue", "R-1", "abc")[0], 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_garde_des_noms_avant_toute_ecriture(self):
        self.texte.write_text(f"Voir {NAME}.", encoding="utf-8")
        code, out, err = self.run_cli("detach-sub-issue", "R-1", "2", "--comment-file", str(self.texte))
        self.assertEqual(code, 3)
        self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.load()["sub"]["1"], [2])

    def test_fichier_de_commentaire_illisible(self):
        code, _, _ = self.run_cli("detach-sub-issue", "R-1", "2", "--comment-file", str(self.texte.with_name("absent.md")))
        self.assertEqual(code, 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_confirmation_du_depot(self):
        self.assertEqual(self.run_cli("detach-sub-issue", "R-1", "2", "--repo", "autre/depot")[0], 2)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.run_cli("detach-sub-issue", "R-1", "2", "--repo", "owner-x/repo-y")[0], 0)


class StatutDUneIdee(Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1)                                    # n°1
        self.add_issue("X", "Une idée", ["type:idea"], body="<!-- roadmap-idea: une-idee -->\n\ntexte")      # n°2

    def statut(self, n):
        return next((i["status"] for i in self.load()["project"]["items"] if i["number"] == n), None)

    def test_statut_d_une_idee_par_diese_ou_numero(self):
        code, out, err = self.run_cli("status", "#2", "In progress")
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: status #2 In progress", out)
        self.assertEqual(self.statut(2), "In progress")
        self.assertEqual(self.run_cli("status", "2", "Ready")[0], 0)
        self.assertEqual(self.statut(2), "Ready")

    def test_rien_ecrit_dans_le_corps_ni_le_jalon_de_l_idee(self):
        avant = self.load()["issues"][1]
        self.run_cli("status", "#2", "In progress")
        self.assertEqual(self.load()["issues"][1], avant)
        self.assertEqual([c for c in self.calls(writes_only=True) if "PATCH" in c["args"]], [])

    def test_meme_statut_rien_a_faire(self):
        self.run_cli("status", "#2", "In progress")
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("status", "#2", "In progress")
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_statut_inconnu_refuse(self):
        code, _, err = self.run_cli("status", "#2", "Blocked")
        self.assertEqual(code, 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_issue_fermee_non_modifiee(self):
        self.st = self.load()
        self.st["issues"][1]["state"] = "closed"
        self.save()
        code, _, err = self.run_cli("status", "#2", "In progress")
        self.assertEqual(code, 7)
        self.assertIn("closed", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_de_ce_qui_n_est_pas_une_idee(self):
        self.assertEqual(self.run_cli("status", "#1", "Ready")[0], 7)
        self.assertEqual(self.run_cli("status", "#99", "Ready")[0], 7)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_une_feature_garde_son_comportement(self):
        self.assertEqual(self.run_cli("status", "R-1", "Ready")[0], 0)
        self.assertEqual(self.status_of("R-1"), "Ready")


if __name__ == "__main__":
    unittest.main()
