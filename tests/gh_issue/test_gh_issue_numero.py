"""
Tests de tools/gh_issue.py : --numero (numéro d'issue GitHub à la place de la clé de feuille de route, R-20261102-65) pour close-step,
comment, edit-task (--title en plus) et la commande reopen-step. Même faux gh que test_gh_issue.py. Cas de départ : une clé portée par
deux issues (R-1/u1), que la clé ne sait pas départager.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import unittest
from pathlib import Path

from test_gh_issue import Base, NAME


class Numero(Base):
    def setUp(self):
        super().setUp()
        self.feature = self.add_feature(1, milestone="Hydra")
        self.premiere = self.add_issue("R-1/u1", "R-1 · Étape", ["type:task", "owner:user"], milestone="Hydra")
        self.doublon = self.add_issue("R-1/u1", "R-1 · Étape bis", ["type:task", "owner:user"], milestone="Hydra")
        self.agent = self.add_issue("R-1/g2", "R-1 · 2. Groupe", ["type:task", "model:sonnet"], milestone="Hydra")
        self.fermee = self.add_issue("R-1/u3", "R-1 · Fermée", ["type:task", "owner:user"], state="closed", milestone="Hydra")
        self.idee = self.add_issue("#idee", "Une idée", ["type:idea"], body="<!-- roadmap-idea -->\n\ntexte")
        self.fichier = Path(self.tmp.name) / "texte.txt"
        self.fichier.write_text("Un commentaire.", encoding="utf-8")

    def etat(self, issue):
        return next(i for i in self.load()["issues"] if i["number"] == issue["number"])

    def n(self, issue):
        return str(issue["number"])

    def aucune_ecriture(self):
        self.assertEqual(self.calls(writes_only=True), [])

    # exclusion de la clé et du numéro, communes aux quatre commandes
    def test_cle_et_numero_ensemble_refuses_code_2(self):
        for argv in (("close-step", "R-1/u1", "--numero", self.n(self.doublon)),
                     ("reopen-step", "R-1/u3", "--numero", self.n(self.fermee), "--reason", "r"),
                     ("edit-task", "R-1/u1", "--numero", self.n(self.doublon), "--title", "T"),
                     ("comment", "R-1", "--numero", self.n(self.feature), "--body-file", str(self.fichier))):
            code, _, err = self.run_cli(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn("either a key or --numero", err, argv)
        self.aucune_ecriture()

    def test_ni_cle_ni_numero_refuse_code_2(self):
        for argv in (("close-step",), ("reopen-step", "--reason", "r"), ("edit-task", "--title", "T"),
                     ("comment", "--body-file", str(self.fichier))):
            code, _, err = self.run_cli(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn("either a key or --numero", err, argv)
        self.aucune_ecriture()

    def test_numero_inconnu_code_7(self):
        for argv in (("close-step", "--numero", "99"), ("reopen-step", "--numero", "99", "--reason", "r"),
                     ("edit-task", "--numero", "99", "--title", "T"),
                     ("comment", "--numero", "99", "--body-file", str(self.fichier))):
            code, _, err = self.run_cli(*argv)
            self.assertEqual(code, 7, argv)
            self.assertIn("unknown issue #99", err, argv)
        self.aucune_ecriture()

    def test_numero_non_entier_code_2(self):
        code, _, _ = self.run_cli("close-step", "--numero", "abc")
        self.assertEqual(code, 2)

    # close-step
    def test_close_step_ferme_la_bonne_issue_parmi_deux_cles_identiques(self):
        code, out, err = self.run_cli("close-step", "--numero", self.n(self.doublon))
        self.assertEqual(code, 0, err)
        self.assertIn(f"closed #{self.doublon['number']}", out)
        self.assertEqual(self.etat(self.doublon)["state"], "closed")
        self.assertEqual(self.etat(self.premiere)["state"], "open")

    def test_close_step_numero_tache_agent_exige_la_raison(self):
        code, _, err = self.run_cli("close-step", "--numero", self.n(self.agent))
        self.assertEqual(code, 7)
        self.assertIn(f"#{self.agent['number']} is an agent sub-issue", err)
        self.aucune_ecriture()
        code, _, err = self.run_cli("close-step", "--numero", self.n(self.agent), "--reason", "fait")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.etat(self.agent)["state"], "closed")

    def test_close_step_mauvais_type_code_2(self):
        for issue in (self.feature, self.idee):
            code, _, err = self.run_cli("close-step", "--numero", self.n(issue))
            self.assertEqual(code, 2)
            self.assertIn("is not a task issue", err)
        self.aucune_ecriture()

    # comment
    def test_comment_par_numero_de_feature(self):
        code, out, err = self.run_cli("comment", "--numero", self.n(self.feature), "--body-file", str(self.fichier))
        self.assertEqual(code, 0, err)
        self.assertIn(f"commented #{self.feature['number']}", out)
        self.assertEqual(self.load()["comments"], [{"issue": self.feature["number"], "body": "Un commentaire."}])

    def test_comment_mauvais_type_code_2(self):
        for issue in (self.premiere, self.idee):
            code, _, err = self.run_cli("comment", "--numero", self.n(issue), "--body-file", str(self.fichier))
            self.assertEqual(code, 2)
            self.assertIn("is not a feature issue", err)
        self.aucune_ecriture()

    # reopen-step
    def test_reopen_step_par_numero_poste_le_motif_puis_rouvre(self):
        code, out, err = self.run_cli("reopen-step", "--numero", self.n(self.fermee), "--reason", "fermée par erreur")
        self.assertEqual(code, 0, err)
        self.assertIn(f"reopened #{self.fermee['number']}", out)
        self.assertEqual(self.etat(self.fermee)["state"], "open")
        self.assertEqual(self.load()["comments"],
                         [{"issue": self.fermee["number"], "body": "<!-- roadmap-reopened -->\nReopened: fermée par erreur"}])
        self.assertEqual([("POST" in c["args"]) for c in self.calls(writes_only=True)], [True, False])

    def test_reopen_step_par_cle(self):
        code, out, err = self.run_cli("reopen-step", "R-1/u3", "--reason", "à refaire")
        self.assertEqual(code, 0, err)
        self.assertIn("reopened R-1/u3", out)
        self.assertEqual(self.etat(self.fermee)["state"], "open")

    def test_reopen_step_deja_ouverte_rien_a_faire(self):
        code, out, err = self.run_cli("reopen-step", "--numero", self.n(self.premiere), "--reason", "r")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.aucune_ecriture()

    def test_reopen_step_motif_vide_code_2(self):
        code, _, err = self.run_cli("reopen-step", "--numero", self.n(self.fermee), "--reason", "   ")
        self.assertEqual(code, 2)
        self.assertIn("--reason must not be empty", err)
        self.aucune_ecriture()

    def test_reopen_step_mauvais_type_ou_cle_de_feature_code_2(self):
        for issue in (self.feature, self.idee):
            code, _, err = self.run_cli("reopen-step", "--numero", self.n(issue), "--reason", "r")
            self.assertEqual(code, 2)
            self.assertIn("is not a task issue", err)
        code, _, err = self.run_cli("reopen-step", "R-1", "--reason", "r")
        self.assertEqual(code, 2)
        self.assertIn("reopen-step expects", err)
        self.aucune_ecriture()

    def test_reopen_step_motif_avec_un_nom_sensible_code_3(self):
        code, out, err = self.run_cli("reopen-step", "--numero", self.n(self.fermee), "--reason", f"voir {NAME}")
        self.assertEqual(code, 3)
        self.no_leak(out, err)
        self.aucune_ecriture()
        self.assertEqual(self.etat(self.fermee)["state"], "closed")

    # edit-task
    def test_edit_task_retitre_la_bonne_issue_par_numero(self):
        code, out, err = self.run_cli("edit-task", "--numero", self.n(self.doublon), "--title", "Étape distincte")
        self.assertEqual(code, 0, err)
        self.assertIn(f"retitled #{self.doublon['number']}", out)
        self.assertEqual(self.etat(self.doublon)["title"], "R-1 · Étape distincte")
        self.assertEqual(self.etat(self.premiere)["title"], "R-1 · Étape")
        ecritures = self.calls(writes_only=True)
        self.assertEqual(len(ecritures), 1)
        self.assertIn("PATCH", ecritures[0]["args"])

    def test_edit_task_meme_titre_rien_a_faire(self):
        code, out, err = self.run_cli("edit-task", "--numero", self.n(self.premiere), "--title", "Étape")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.aucune_ecriture()

    def test_edit_task_titre_vide_ou_avec_cle_code_2(self):
        for titre in ("  ", "R-1 · Autre"):
            code, _, _ = self.run_cli("edit-task", "--numero", self.n(self.doublon), "--title", titre)
            self.assertEqual(code, 2, titre)
        self.aucune_ecriture()

    def test_edit_task_titre_avec_un_nom_sensible_code_3(self):
        code, out, err = self.run_cli("edit-task", "--numero", self.n(self.doublon), "--title", f"Étape {NAME}")
        self.assertEqual(code, 3)
        self.no_leak(out, err)
        self.aucune_ecriture()

    def test_edit_task_sans_option_code_2(self):
        code, _, err = self.run_cli("edit-task", "--numero", self.n(self.doublon))
        self.assertEqual(code, 2)
        self.assertIn("--milestone and/or --title", err)
        self.aucune_ecriture()

    def test_edit_task_mauvais_type_code_2(self):
        for issue in (self.feature, self.idee):
            code, _, err = self.run_cli("edit-task", "--numero", self.n(issue), "--title", "T")
            self.assertEqual(code, 2)
            self.assertIn("is not a task issue", err)
        self.aucune_ecriture()

    def test_edit_task_jalon_par_numero(self):
        code, out, err = self.run_cli("edit-task", "--numero", self.n(self.doublon), "--milestone", "Namazu")
        self.assertEqual(code, 0, err)
        self.assertIn(f"moved #{self.doublon['number']}", out)
        self.assertEqual(self.etat(self.doublon)["milestone"]["title"], "Namazu")
        self.assertEqual(self.etat(self.premiere)["milestone"]["title"], "Hydra")

    def test_edit_task_titre_seul_admis_sur_une_tache_fermee_jalon_non(self):
        code, _, err = self.run_cli("edit-task", "--numero", self.n(self.fermee), "--title", "Renommée")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.etat(self.fermee)["title"], "R-1 · Renommée")
        code, _, err = self.run_cli("edit-task", "--numero", self.n(self.fermee), "--milestone", "Namazu")
        self.assertEqual(code, 2)
        self.assertIn("closed", err)

    def test_edit_task_jalon_et_titre_ensemble(self):
        code, _, err = self.run_cli("edit-task", "--numero", self.n(self.doublon), "--milestone", "Namazu", "--title", "Les deux")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.etat(self.doublon)["title"], "R-1 · Les deux")
        self.assertEqual(self.etat(self.doublon)["milestone"]["title"], "Namazu")
        self.assertEqual(len(self.calls(writes_only=True)), 2)


    # compléments de revue (suite de la classe Numero)
    def test_reopen_step_refuse_une_tache_de_tasks_md_code_2(self):
        patch = self.add_issue("R-1/t1.1", "R-1 · 1.1 Tâche", ["type:task", "owner:user"], state="closed", milestone="Hydra")
        for argv in (("reopen-step", "--numero", self.n(patch), "--reason", "r"), ("reopen-step", "R-1/t1.1", "--reason", "r")):
            code, _, err = self.run_cli(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn("tasks.md task", err)
            self.assertIn("sync-tasks will reopen it", err)
        code, _, err = self.run_cli("reopen-step", "--numero", self.n(self.agent), "--reason", "r")
        self.assertEqual(code, 2)
        self.aucune_ecriture()

    def test_reopen_step_jalon_ferme_code_7_avant_toute_ecriture(self):
        vieille = self.add_issue("R-1/u4", "R-1 · Vieille", ["type:task", "owner:user"], state="closed", milestone="Tarasque")
        code, _, err = self.run_cli("reopen-step", "--numero", self.n(vieille), "--reason", "r")
        self.assertEqual(code, 7)
        self.assertIn("closed milestone", err)
        self.aucune_ecriture()
        self.assertEqual(self.etat(vieille)["state"], "closed")

    def test_close_step_apres_une_reouverture_poste_le_nouveau_motif(self):
        n = self.n(self.premiere)
        self.assertEqual(self.run_cli("close-step", "--numero", n, "--reason", "R1")[0], 0)
        self.assertEqual(self.run_cli("reopen-step", "--numero", n, "--reason", "X")[0], 0)
        code, _, err = self.run_cli("close-step", "--numero", n, "--reason", "R2")
        self.assertEqual(code, 0, err)
        corps = [c["body"] for c in self.load()["comments"]]
        self.assertEqual(len(corps), 3)
        self.assertEqual(corps[-1], "<!-- roadmap-closed-with-reason -->\nClosed with a reason: R2")
        self.assertEqual(self.etat(self.premiere)["state"], "closed")

    def test_close_step_deux_fois_sans_reouverture_ne_reposte_pas(self):
        n = self.n(self.premiere)
        self.run_cli("close-step", "--numero", n, "--reason", "R1")
        self.run_cli("close-step", "--numero", n, "--reason", "R1")
        self.assertEqual(len(self.load()["comments"]), 1)

    def test_comment_numero_avec_un_nom_sensible_code_3(self):
        mauvais = Path(self.tmp.name) / "mauvais.txt"
        mauvais.write_text(f"voir {NAME}", encoding="utf-8")
        code, out, err = self.run_cli("comment", "--numero", self.n(self.feature), "--body-file", str(mauvais))
        self.assertEqual(code, 3)
        self.no_leak(out, err)
        self.aucune_ecriture()

    def test_numero_sur_une_tache_sans_owner_ni_model_se_comporte_comme_une_tache_d_agent(self):
        sans = self.add_issue("R-1/u5", "R-1 · Sans", ["type:task"], milestone="Hydra")
        code, _, err = self.run_cli("close-step", "--numero", self.n(sans))
        self.assertEqual(code, 7)
        self.assertIn("is an agent sub-issue", err)
        self.aucune_ecriture()
        self.assertEqual(self.run_cli("close-step", "--numero", self.n(sans), "--reason", "ok")[0], 0)

    def test_pas_d_appel_gh_hors_outil_partage(self):
        src = (Path(__file__).resolve().parents[2] / "tools" / "gh_issue.py").read_text(encoding="utf-8")
        for nom in ("def cmd_reopen_step", "def issue_by_numero", "def task_target"):
            debut = src.index(nom)
            corps = src[debut:src.index("\ndef ", debut + 10)]
            self.assertNotIn("subprocess", corps, nom)
            self.assertNotIn("gh_run", corps, nom)


class NouvelleCle(Base):
    def setUp(self):
        super().setUp()
        self.feature = self.add_feature(1, milestone="Hydra")
        self.premiere = self.add_issue("R-1/u1", "R-1 · Étape", ["type:task", "owner:user"], milestone="Hydra")
        self.doublon = self.add_issue("R-1/u1", "R-1 · Étape bis", ["type:task", "owner:user"], milestone="Hydra",
                                      body="<!-- roadmap-id: R-1/u1 -->\n\nTexte du corps.\nDeuxième ligne.")
        self.fermee = self.add_issue("R-1/u2", "R-1 · Fermée", ["type:task", "owner:user"], state="closed", milestone="Hydra")
        self.idee = self.add_issue("#idee", "Une idée", ["type:idea"], body="<!-- roadmap-idea -->\n\ntexte")

    def etat(self, issue):
        return next(i for i in self.load()["issues"] if i["number"] == issue["number"])

    def test_la_seconde_recoit_la_prochaine_cle_libre_corps_et_titre(self):
        code, out, err = self.run_cli("edit-task", "--numero", str(self.doublon["number"]), "--nouvelle-cle")
        self.assertEqual(code, 0, err)
        self.assertIn(f"rekeyed #{self.doublon['number']} : R-1/u1 -> R-1/u3", out)
        e = self.etat(self.doublon)
        self.assertEqual(e["body"], "<!-- roadmap-id: R-1/u3 -->\n\nTexte du corps.\nDeuxième ligne.")
        self.assertEqual(e["title"], "R-1 · Étape bis")
        self.assertEqual(self.etat(self.premiere)["body"], "<!-- roadmap-id: R-1/u1 -->")
        ecritures = self.calls(writes_only=True)
        self.assertEqual(len(ecritures), 1)
        self.assertIn("PATCH", ecritures[0]["args"])

    def test_avec_title_une_seule_ecriture(self):
        code, _, err = self.run_cli("edit-task", "--numero", str(self.doublon["number"]), "--nouvelle-cle", "--title", "Distincte")
        self.assertEqual(code, 0, err)
        e = self.etat(self.doublon)
        self.assertEqual(e["title"], "R-1 · Distincte")
        self.assertTrue(e["body"].startswith("<!-- roadmap-id: R-1/u3 -->"))
        self.assertEqual(len(self.calls(writes_only=True)), 1)

    def test_les_numeros_comptent_les_issues_fermees(self):
        # R-1/u2 est portée par une issue fermée : la nouvelle clé est u3, pas u2
        self.run_cli("edit-task", "--numero", str(self.doublon["number"]), "--nouvelle-cle")
        self.assertIn("R-1/u3", self.etat(self.doublon)["body"])

    def test_cle_deja_unique_rien_a_faire(self):
        code, out, err = self.run_cli("edit-task", "--numero", str(self.fermee["number"]), "--nouvelle-cle")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_rejeu_apres_la_reecriture_rien_a_faire(self):
        n = str(self.doublon["number"])
        self.run_cli("edit-task", "--numero", n, "--nouvelle-cle")
        ecrit = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("edit-task", "--numero", n, "--nouvelle-cle")
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), ecrit)

    def test_feature_et_idee_refusees_code_2(self):
        for issue in (self.feature, self.idee):
            code, _, err = self.run_cli("edit-task", "--numero", str(issue["number"]), "--nouvelle-cle")
            self.assertEqual(code, 2)
            self.assertIn("is not a task issue", err)
        code, _, _ = self.run_cli("edit-task", "R-1", "--nouvelle-cle")
        self.assertEqual(code, 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_tache_fermee_dupliquee_acceptee(self):
        dup = self.add_issue("R-1/u2", "R-1 · Fermée bis", ["type:task", "owner:user"], state="closed", milestone="Hydra")
        code, out, err = self.run_cli("edit-task", "--numero", str(dup["number"]), "--nouvelle-cle")
        self.assertEqual(code, 0, err)
        self.assertIn("-> R-1/u3", out)

    def test_cle_portee_par_plusieurs_issues_refusee_code_2_utiliser_numero(self):
        code, _, err = self.run_cli("edit-task", "R-1/u1", "--nouvelle-cle")
        self.assertEqual(code, 2)
        self.assertIn("use --numero", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_cle_unique_par_cle_fonctionne_rien_a_faire(self):
        code, out, err = self.run_cli("edit-task", "R-1/u2", "--nouvelle-cle")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)

    def test_corps_reecrit_avec_un_nom_sensible_code_3_rien_ecrit(self):
        sale = self.add_issue("R-1/u1", "R-1 · Sale", ["type:task", "owner:user"], milestone="Hydra",
                              body=f"<!-- roadmap-id: R-1/u1 -->\n\nvoir {NAME}")
        code, out, err = self.run_cli("edit-task", "--numero", str(sale["number"]), "--nouvelle-cle")
        self.assertEqual(code, 3)
        self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertTrue(self.etat(sale)["body"].startswith("<!-- roadmap-id: R-1/u1 -->"))


if __name__ == "__main__":
    unittest.main()
