"""
Tests de tools/gh_issue.py : promotion d'une idée en feature (groupe 2) et rattachement d'une issue comme sous-issue
(groupe 3), change gh-issue-autonomy, design D2 et D3. Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest

from test_gh_issue import Base, NAME, FAKE_KEY, g, rm


# --- Groupe 2 : promotion d'une idée (design D2) ----------------------------------------------------------------------

class PromotionDUneIdee(Base):
    TITRE = "Une idée à promouvoir"
    TEXTE = "Le texte de l'idée.\n\nUne seconde ligne."

    def idee(self, labels=("type:idea", "value:2"), state="open", texte=None, milestone=None, titre=None, slug="une-idee"):
        body = f"{rm.idea_marker(slug)}\n\n{texte or self.TEXTE}"
        return self.add_issue("R-1", titre or self.TITRE, list(labels), body=body, state=state, milestone=milestone)

    def raw(self, n):
        return next(i for i in self.load()["issues"] if i["number"] == n)

    def etiquettes(self, n):
        return sorted(l["name"] for l in self.raw(n)["labels"])

    def patchs(self):
        return [c for c in self.calls(writes_only=True) if "PATCH" in c["args"]]

    def test_promotion_titre_corps_etiquettes_et_une_seule_requete(self):
        self.add_feature(4)
        idee = self.idee(labels=("type:idea", "value:2", "product:mothra"))
        n = idee["number"]
        code, out, err = self.run_cli("promote-idea", str(n), "--theme", "outillage")
        self.assertEqual(code, 0, err)
        self.assertIn(f"gh_issue: promoted #{n} to R-5", out)
        issue = self.raw(n)
        self.assertEqual(issue["title"], f"R-5 {rm.SEP} {self.TITRE}")
        self.assertEqual(rm.parse_marker(issue["body"]), "R-5")
        self.assertIsNone(rm.parse_idea_marker(issue["body"]))
        self.assertNotIn("roadmap-idea", issue["body"])
        self.assertIn(self.TEXTE, issue["body"])
        block = rm.parse_block(issue["body"])
        self.assertEqual((block["id"], block["theme"], block["rank"]), ("R-5", "outillage", 50))
        self.assertEqual(self.etiquettes(n), sorted(["type:feature", "theme:outillage", "value:2", "product:mothra"]))
        self.assertEqual(len(self.patchs()), 1)       # aucune issue à moitié promue
        payload = json.loads(self.patchs()[0]["stdin"])
        self.assertEqual(sorted(payload), ["body", "labels", "title"])

    def test_jalon_garde(self):
        idee = self.idee(milestone="Namazu")
        self.assertEqual(self.run_cli("promote-idea", f"#{idee['number']}", "--theme", "base")[0], 0)
        self.assertEqual(self.raw(idee["number"])["milestone"]["title"], "Namazu")
        self.assertNotIn("milestone", json.loads(self.patchs()[0]["stdin"]))

    def test_idee_sans_jalon_reste_sans_jalon(self):
        idee = self.idee()
        self.assertEqual(self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")[0], 0)
        self.assertIsNone(self.raw(idee["number"])["milestone"])

    def test_set_et_rang(self):
        idee = self.idee()
        code, _, err = self.run_cli("promote-idea", str(idee["number"]), "--theme", "base", "--set", "rank=7", "--set", "estimate=2h")
        self.assertEqual(code, 0, err)
        block = rm.parse_block(self.raw(idee["number"])["body"])
        self.assertEqual((block["rank"], block["estimate"]), (7, "2h"))

    def test_project_statut_todo_par_defaut(self):
        idee = self.idee()
        self.assertEqual(self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")[0], 0)
        self.assertEqual(self.status_of("R-1"), "Todo")

    def test_project_statut_de_l_idee_garde(self):
        idee = self.idee()
        self.st = self.load()
        self.st["project"]["items"].append({"id": "PVTI_x", "number": idee["number"], "status": "Ready"})
        self.save()
        self.assertEqual(self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")[0], 0)
        self.assertEqual(self.status_of("R-1"), "Ready")

    def test_deuxieme_lancement_rien_a_faire(self):
        idee = self.idee()
        self.assertEqual(self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")[0], 0)
        avant = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")
        self.assertEqual(code, 0, err)
        self.assertIn(f"nothing to do: #{idee['number']} is already R-1", out)
        self.assertEqual(len(self.calls(writes_only=True)), avant)

    def test_lancement_interrompu_complete_le_project(self):
        idee = self.idee()
        self.assertEqual(self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")[0], 0)
        self.st = self.load()
        self.st["project"]["items"] = []      # l'ajout au Project n'a pas eu lieu
        self.save()
        code, out, err = self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(self.status_of("R-1"), "Todo")
        self.assertEqual(len(self.patchs()), 1)

    def test_feature_fermee_hors_du_project_n_y_est_pas_remise(self):
        idee = self.idee()
        self.assertEqual(self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")[0], 0)
        self.st = self.load()
        self.st["project"]["items"] = []
        for i in self.st["issues"]:
            if i["number"] == idee["number"]:
                i["state"], i["state_reason"] = "closed", "not_planned"
        self.save()
        avant = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), avant)
        self.assertEqual(self.load()["project"]["items"], [])

    def test_refus_sans_ecriture(self):
        self.add_feature(4, rank=50)
        cas = [("une feature sans marqueur", lambda: self.add_issue("R-9", "x", ["type:feature"], body="sans marqueur"), 7, "not an idea"),
               ("une issue sans type", lambda: self.add_issue("R-1", "x", [], body="rien"), 7, "not an idea"),
               ("une idée fermée", lambda: self.idee(state="closed"), 7, "is closed; reopen it before promoting it")]
        for nom, seme, code_attendu, message in cas:
            with self.subTest(nom):
                n = seme()["number"]
                debut = len(self.calls(writes_only=True))
                code, out, err = self.run_cli("promote-idea", str(n), "--theme", "base")
                self.assertEqual(code, code_attendu, err)
                self.assertIn(message, err)
                self.assertEqual(len(self.calls(writes_only=True)), debut)

    def test_refus_numero_inconnu_et_mal_forme(self):
        self.assertEqual(self.run_cli("promote-idea", "99", "--theme", "base")[0], 7)
        self.assertEqual(self.run_cli("promote-idea", "R-3", "--theme", "base")[0], 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_theme_inconnu(self):
        idee = self.idee()
        code, _, err = self.run_cli("promote-idea", str(idee["number"]), "--theme", "nimporte")
        self.assertEqual(code, 2, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_rang_pris(self):
        self.add_feature(4, rank=50)
        idee = self.idee()
        code, _, err = self.run_cli("promote-idea", str(idee["number"]), "--theme", "base", "--set", "rank=50")
        self.assertEqual(code, 7, err)
        self.assertIn("rank already used by R-4", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_bloc_invalide(self):
        idee = self.idee()
        code, _, err = self.run_cli("promote-idea", str(idee["number"]), "--theme", "base", "--set", "estimate=nimporte quoi")
        self.assertEqual(code, 7, err)
        self.assertIn("invalid block", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_cle_deja_portee(self):
        # la clé suivante vient du plus grand identifiant lu, donc libre en pratique ; la vérification de D1 est testée sur le service
        porteuse = self.add_issue("R-4", "autre", ["type:task"], state="closed")
        ctx = g.Ctx(g.Client(g.Guard.load()))
        with self.assertRaises(g.Stop) as e:
            g.check_key_free(ctx.snap, "R-4")
        self.assertEqual(e.exception.code, 7)
        self.assertEqual(e.exception.lines, [f"duplicate key R-4: already carried by #{porteuse['number']}; nothing was sent"])
        g.check_key_free(ctx.snap, "R-5")      # une clé libre ne lève rien

    def test_garde_titre_et_corps_sans_ecriture(self):
        for nom, kw in (("titre", {"titre": f"Idée de {NAME}"}), ("corps", {"texte": f"voir {FAKE_KEY}"})):
            with self.subTest(nom):
                idee = self.idee(**kw)
                code, out, err = self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")
                self.assertEqual(code, 3, err)
                self.assertEqual(self.calls(writes_only=True), [])
                self.no_leak(out, err)

    def test_garde_theme_et_valeur_du_set(self):
        idee = self.idee()
        code, out, err = self.run_cli("promote-idea", str(idee["number"]), "--theme", "base", "--set", f"conditions={NAME} attend")
        self.assertEqual(code, 3, err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.no_leak(out, err)

    def test_idee_reenregistree_apres_promotion(self):
        """Le marqueur d'idée est retiré : le même titre peut être enregistré de nouveau (design D2)."""
        idee = self.idee(slug="une-idee-a-promouvoir")
        self.assertEqual(self.run_cli("promote-idea", str(idee["number"]), "--theme", "base")[0], 0)
        code, out, err = self.run_cli("new-idea", "--title", self.TITRE, "--body", "Autre texte.")
        self.assertEqual(code, 0, err)
        self.assertIn("created idea", out)


# --- Groupe 3 : rattacher une issue comme sous-issue (design D3) -----------------------------------------------------------

class RattacherUneSousIssue(Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1)
        self.add_feature(2, milestone="Hydra")

    def enfant(self, key="R-1/u1", state="open", milestone="Hydra", body=None):
        return self.add_issue(key, f"R-1 {rm.SEP} tâche", ["type:task", "owner:user"], state=state, milestone=milestone, body=body)

    def sous(self, parent):
        return self.load().get("sub", {}).get(str(parent), [])

    def pose(self, parent, *enfants):
        self.st = self.load()
        self.st.setdefault("sub", {})[str(parent)] = list(enfants)
        self.save()

    def test_rattache_par_cle_et_par_numero(self):
        e = self.enfant()
        code, out, err = self.run_cli("attach-sub-issue", "R-1", str(e["number"]))
        self.assertEqual(code, 0, err)
        self.assertIn(f"gh_issue: attached #{e['number']} to #1", out)
        self.assertEqual(self.sous(1), [e["number"]])
        self.st = self.load()      # le faux GitHub a écrit : repartir de son état
        f = self.enfant("R-1/u2")
        self.assertEqual(self.run_cli("attach-sub-issue", "#1", f"#{f['number']}")[0], 0)
        self.assertEqual(self.sous(1), [e["number"], f["number"]])

    def test_enfant_designe_par_sa_cle(self):
        e = self.add_feature(3)
        code, out, err = self.run_cli("attach-sub-issue", "R-1", "R-3")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.sous(1), [e["number"]])

    def test_une_seule_ecriture_sans_remplacement_de_parent(self):
        e = self.enfant()
        self.run_cli("attach-sub-issue", "R-1", str(e["number"]))
        ecritures = self.calls(writes_only=True)
        self.assertEqual(len(ecritures), 1)
        self.assertEqual(json.loads(ecritures[0]["stdin"]), {"sub_issue_id": e["id"]})

    def test_deuxieme_lancement_rien_a_faire(self):
        e = self.enfant()
        self.pose(1, e["number"])
        code, out, err = self.run_cli("attach-sub-issue", "R-1", str(e["number"]))
        self.assertEqual(code, 0, err)
        self.assertIn(f"nothing to do: #{e['number']} is already a sub-issue of #1", out)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_ecart_de_jalon_rapporte_sans_deplacement(self):
        e = self.enfant(milestone="Namazu")
        code, out, err = self.run_cli("attach-sub-issue", "R-1", str(e["number"]))
        self.assertEqual(code, 0, err)
        self.assertIn(f"gh_issue: milestone differs: #{e['number']} Namazu, #1 Hydra", out)
        self.assertEqual(self.milestone_writes(), [])
        self.assertEqual(self.load()["issues"][e["number"] - 1]["milestone"]["title"], "Namazu")

    def test_ecart_de_jalon_sans_jalon(self):
        e = self.enfant(milestone=None)
        code, out, _ = self.run_cli("attach-sub-issue", "R-1", str(e["number"]))
        self.assertEqual(code, 0)
        self.assertIn(f"milestone differs: #{e['number']} none, #1 Hydra", out)

    def test_meme_jalon_pas_de_ligne(self):
        e = self.enfant()
        _, out, _ = self.run_cli("attach-sub-issue", "R-1", str(e["number"]))
        self.assertNotIn("milestone differs", out)

    def test_refus_sans_ecriture(self):
        e = self.enfant()
        fermee = self.add_feature(5, state="closed")
        n_e = e["number"]
        cas = [("soi-même", ("R-1", "R-1"), 2, "an issue cannot be its own sub-issue"),
               ("enfant inconnu", ("R-1", "99"), 7, "unknown issue 99"),
               ("parent inconnu", ("R-99", str(n_e)), 7, "unknown identifier R-99"),
               ("parent fermé", ("R-5", str(n_e)), 7, f"#{fermee['number']} is closed; nothing was sent"),
               ("référence mal formée", ("feature", str(n_e)), 2, "usage:")]
        for nom, argv, code_attendu, message in cas:
            with self.subTest(nom):
                code, out, err = self.run_cli("attach-sub-issue", *argv)
                self.assertEqual(code, code_attendu, err)
                self.assertIn(message, err)
                self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_cycle(self):
        # R-2 est sous-issue de R-1 : rattacher R-1 sous R-2 fermerait la boucle
        self.pose(1, self.number_of("R-2"))
        code, _, err = self.run_cli("attach-sub-issue", "R-2", "R-1")
        self.assertEqual(code, 7, err)
        self.assertIn("#2 is a sub-issue of #1; nothing was sent", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_cle_en_double(self):
        deja = self.enfant("R-1/u1")
        self.pose(1, deja["number"])
        doublon = self.enfant("R-1/u1")
        code, _, err = self.run_cli("attach-sub-issue", "R-1", str(doublon["number"]))
        self.assertEqual(code, 7, err)
        self.assertIn(f"duplicate key R-1/u1: already carried by #{deja['number']} under #1; nothing was sent", err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.sous(1), [deja["number"]])

    def test_enfant_sans_cle_se_rattache(self):
        e = self.add_issue("R-1/u1", "libre", ["type:task"], body="texte sans marqueur")
        code, _, err = self.run_cli("attach-sub-issue", "R-1", str(e["number"]))
        self.assertEqual(code, 0, err)

    def test_github_refuse_un_enfant_deja_sous_un_autre_parent(self):
        e = self.enfant()
        self.pose(2, e["number"])
        code, out, err = self.run_cli("attach-sub-issue", "R-1", str(e["number"]))
        self.assertEqual(code, 1, err)
        self.assertIn("GitHub refused", err)
        self.assertEqual(self.sous(2), [e["number"]])
        self.assertEqual(self.sous(1), [])
        self.no_leak(out, err)

    def test_aucun_texte_envoye_donc_rien_a_garder(self):
        e = self.enfant()
        self.run_cli("attach-sub-issue", "R-1", str(e["number"]))
        for c in self.calls(writes_only=True):
            self.assertEqual(set(json.loads(c["stdin"])), {"sub_issue_id"})

    def test_inverse_de_detach(self):
        e = self.enfant()
        self.assertEqual(self.run_cli("attach-sub-issue", "R-1", str(e["number"]))[0], 0)
        self.assertEqual(self.run_cli("detach-sub-issue", "R-1", str(e["number"]))[0], 0)
        self.assertEqual(self.sous(1), [])
        self.assertEqual(self.run_cli("attach-sub-issue", "R-1", str(e["number"]))[0], 0)
        self.assertEqual(self.sous(1), [e["number"]])


if __name__ == "__main__":
    unittest.main()
