"""
Tests de tools/gh_issue.py : --value sur new-feature et edit (idée #512), fermeture d'une feature remplacée ou abandonnée
close-feature --reason replaced|dropped (idée #524). Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest
from pathlib import Path

import roadmap_model as rm
from test_gh_issue import Base, NAME


def noms(issue):
    return sorted(l["name"] for l in issue["labels"])


class ValeurSurLesFeatures(Base):
    def test_new_feature_pose_value(self):
        code, _, err = self.run_cli("new-feature", "--title", "Écran", "--theme", "outillage", "--milestone", "Hydra", "--value", "2")
        self.assertEqual(code, 0, err)
        self.assertIn("value:2", noms(self.issue("R-1")))
        self.assertIn("value:2", [l["name"] for l in self.load()["labels"]])

    def test_new_feature_sans_option_pas_de_value(self):
        self.run_cli("new-feature", "--title", "Écran", "--theme", "outillage", "--milestone", "Hydra")
        self.assertEqual([l for l in noms(self.issue("R-1")) if l.startswith("value:")], [])

    def test_valeur_hors_echelle_refusee(self):
        code, _, err = self.run_cli("new-feature", "--title", "X", "--theme", "outillage", "--milestone", "Hydra", "--value", "4")
        self.assertEqual(code, 2)
        self.add_feature(1)
        self.assertEqual(self.run_cli("edit", "R-1", "--value", "0")[0], 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_edit_pose_remplace_puis_rien_a_faire(self):
        self.add_feature(1)
        code, _, err = self.run_cli("edit", "R-1", "--value", "1")
        self.assertEqual(code, 0, err)
        self.assertEqual(noms(self.issue("R-1")), ["theme:outillage", "type:feature", "value:1"])
        code, _, err = self.run_cli("edit", "R-1", "--value", "3")
        self.assertEqual(code, 0, err)
        self.assertEqual(noms(self.issue("R-1")), ["theme:outillage", "type:feature", "value:3"])
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("edit", "R-1", "--value", "3")
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_edit_sans_value_laisse_la_valeur_intacte(self):
        self.add_feature(1)
        self.run_cli("edit", "R-1", "--value", "2")
        code, _, err = self.run_cli("edit", "R-1", "--title", "Nouveau titre")
        self.assertEqual(code, 0, err)
        self.assertIn("value:2", noms(self.issue("R-1")))

    def test_edit_value_garde_les_autres_labels(self):
        self.add_feature(1)
        self.run_cli("edit", "R-1", "--product", "mothra", "--value", "2")
        self.assertEqual(noms(self.issue("R-1")), ["product:mothra", "theme:outillage", "type:feature", "value:2"])


class FermetureRemplaceeOuAbandonnee(Base):
    def setUp(self):
        super().setUp()
        self.texte = Path(self.tmp.name) / "remplace.md"
        self.texte.write_text("Remplacée par R-9 : le travail n'est pas fusionné.", encoding="utf-8")

    def close(self, *extra, key="R-1"):
        return self.run_cli("close-feature", key, *extra, "--comment-file", str(self.texte))

    def test_ferme_not_planned_avec_le_commentaire(self):
        self.add_feature(1, status="In progress")
        code, out, err = self.close("--reason", "replaced")
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: closed R-1", out)
        self.assertEqual(self.issue("R-1")["state"], "closed")
        self.assertEqual(self.issue("R-1")["state_reason"], "not_planned")
        cs = self.load()["comments"]
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0]["body"], "<!-- roadmap-close-unmerged -->\nRemplacée par R-9 : le travail n'est pas fusionné.")

    def test_abandonnee_meme_comportement(self):
        self.add_feature(1, status="In progress")
        code, _, err = self.close("--reason", "dropped")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.issue("R-1")["state_reason"], "not_planned")

    def test_pas_de_champs_de_fin(self):
        self.add_feature(1, status="In progress")
        self.close("--reason", "replaced")
        self.assertEqual(self.status_of("R-1"), "In progress")
        self.assertNotIn("done_on", rm.parse_block(self.issue("R-1")["body"]))
        self.assertNotIn("edition:public", noms(self.issue("R-1")))

    def test_les_features_dependantes_restent_bloquees(self):
        self.add_feature(1, status="In progress")
        self.add_feature(2, blocked_by=(1,))
        code, out, err = self.close("--reason", "replaced")
        self.assertEqual(code, 0, err)
        self.assertIn("still blocked", out)
        self.assertIn("R-2", out)
        self.assertNotIn("unblocked", out)
        self.assertEqual(self.load()["blocked"][str(self.number_of("R-2"))], [self.number_of("R-1")])

    def test_rejeu_ne_double_pas_le_commentaire(self):
        self.add_feature(1, status="In progress")
        self.close("--reason", "replaced")
        n = len(self.calls(writes_only=True))
        code, out, _ = self.close("--reason", "replaced")
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.load()["comments"]), 1)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_usage(self):
        self.add_feature(1, status="In progress")
        self.assertEqual(self.run_cli("close-feature", "R-1", "--reason", "replaced")[0], 2)           # commentaire obligatoire
        self.assertEqual(self.close("--reason", "autre")[0], 2)                                         # valeur inconnue
        self.assertEqual(self.close("--reason", "replaced", "--after-merge")[0], 2)                     # incompatible
        self.assertEqual(self.close("--reason", "replaced", "--edition-public")[0], 2)
        self.assertEqual(self.run_cli("close-feature", "R-1", "--reason", "replaced", "--comment-file", str(self.texte.with_name("absent.md")))[0], 2)
        self.texte.write_text(" \n", encoding="utf-8")
        self.assertEqual(self.close("--reason", "replaced")[0], 2)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.issue("R-1")["state"], "open")

    def test_garde_des_noms(self):
        self.add_feature(1, status="In progress")
        self.texte.write_text(f"Remplacée à la demande de {NAME}.", encoding="utf-8")
        code, out, err = self.close("--reason", "replaced")
        self.assertEqual(code, 3)
        self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.issue("R-1")["state"], "open")

    def test_sous_issues_ouvertes_refus_code_7(self):
        self.add_feature(1, change="demo", status="In progress")
        self.run_cli("sync-tasks", "R-1")
        n = len(self.calls(writes_only=True))
        code, _, err = self.close("--reason", "replaced")
        self.assertEqual(code, 7)
        self.assertIn("open sub-issues remain", err)
        self.assertEqual(self.issue("R-1")["state"], "open")
        self.assertEqual(self.load().get("comments", []), [])
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_deja_fermee_completed_refus_code_7_sans_ecriture(self):
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1")
        n = len(self.calls(writes_only=True))
        code, _, err = self.close("--reason", "replaced")
        self.assertEqual(code, 7)
        self.assertIn("already closed as completed", err)
        self.assertEqual(self.issue("R-1")["state_reason"], "completed")
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_ancien_marqueur_ne_tient_pas_lieu_de_motif(self):
        self.add_feature(1, status="In progress")
        self.st = self.load()
        self.st.setdefault("comments", []).append({"issue": self.number_of("R-1"), "body": "<!-- roadmap-close -->\nClosed on branch x, before the merge."})
        self.save()
        code, _, err = self.close("--reason", "replaced")
        self.assertEqual(code, 0, err)
        corps = [c["body"] for c in self.load()["comments"]]
        self.assertEqual(len(corps), 2)
        self.assertTrue(corps[1].startswith("<!-- roadmap-close-unmerged -->\n"))
        self.assertEqual(self.issue("R-1")["state_reason"], "not_planned")

    def test_rejeu_avec_l_autre_valeur_rien_a_faire(self):
        self.add_feature(1, status="In progress")
        self.close("--reason", "replaced")
        code, out, _ = self.close("--reason", "dropped")
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)

    def test_un_bloqueur_abandonne_ne_debloque_pas(self):
        self.add_feature(1, status="In progress")
        self.add_feature(2, status="In progress")
        self.add_feature(3, status="Todo", blocked_by=[1, 2])
        self.close("--reason", "dropped", key="R-1")
        code, out, err = self.run_cli("close-feature", "R-2")
        self.assertEqual(code, 0, err)
        self.assertIn("unblocked: none", out)

    def test_sans_l_option_comportement_inchange(self):
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1")
        self.assertEqual(self.issue("R-1")["state_reason"], "completed")
        self.assertEqual(self.status_of("R-1"), "Done")


if __name__ == "__main__":
    unittest.main()
