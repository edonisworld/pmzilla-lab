"""
finish-single-b3-b6, B6 (design D21) : après un train fusionné (code 0, sens « fusionné »), le train retire la note de relais de chaque branche
fusionnée (dossier pmzilla-notes du dossier Git commun, nom encodé comme le faisait l'ancienne fin unitaire) et dit « note de relais retirée : <branche> »
quand elle existait ; jamais après un autre code, ni pour un essai ni pour une réponse « n » ; un retrait qui échoue est une cause du code 75.
Dépôts jetables réels ; le retrait en échec est une vraie note qui est un dossier non vide (rm sans -r refuse).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain  # noqa: E402


class NoteDeRelais(AvecTrain):
    def note(self, branche: str) -> Path:
        return self.t.commun() / "pmzilla-notes" / branche.replace("%", "%25").replace("/", "%2F")

    def pose(self, *branches: str):
        for b in branches:
            n = self.note(b)
            n.parent.mkdir(parents=True, exist_ok=True)
            n.write_text("prête pour la fin\n", encoding="utf-8")

    def test_la_note_de_chaque_branche_fusionnee_est_retiree_et_celle_d_une_autre_reste(self):
        x, y = self.deux_branches()
        self.pose(x, y, "feat/autre")
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, f"finish_train : note de relais retirée : {x}", f"finish_train : note de relais retirée : {y}")
        self.assertFalse(self.note(x).exists())
        self.assertFalse(self.note(y).exists())
        self.assertTrue(self.note("feat/autre").exists())

    def test_une_branche_sans_note_ne_dit_rien(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "note de relais")

    def test_la_note_reste_apres_un_essai(self):
        self.t.branche("feat/x")
        self.pose("feat/x")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.assertTrue(self.note("feat/x").exists())

    def test_la_note_reste_apres_une_reponse_non(self):
        self.t.branche("feat/x")
        self.pose("feat/x")
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertTrue(self.note("feat/x").exists())
        self.absent(r, "note de relais retirée")

    def test_la_note_reste_apres_un_refus_a_l_admission(self):
        self.t.branche("feat/x")
        self.pose("feat/x")
        (self.t.dossier_worktree("feat/x") / "sale.txt").write_text("x\n", encoding="utf-8")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 62, r.texte)
        self.assertTrue(self.note("feat/x").exists())

    def test_la_note_reste_apres_un_push_refuse_code_74(self):
        self.t.branche("feat/x")
        self.pose("feat/x")
        self.t.refuser_le_push(True)
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 74, r.texte)
        self.assertTrue(self.note("feat/x").exists())

    def test_la_note_reste_apres_un_code_75_pour_une_autre_cause(self):
        self.t.branche("feat/x")
        self.pose("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_IGNORE_DANS": str(self.t.dossier_worktree("feat/x"))}, entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        self.assertTrue(self.note("feat/x").exists())
        self.absent(r, "note de relais retirée")

    def test_un_retrait_en_echec_est_une_cause_du_code_75(self):
        self.t.branche("feat/x")
        n = self.note("feat/x")
        (n / "dedans").mkdir(parents=True)
        (n / "dedans" / "f").write_text("x\n", encoding="utf-8")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        self.contient(r, "  - note de relais non retirée : feat/x", "train fusionné et poussé, fin incomplète")
        self.assertEqual(self.t.main(), self.t.origin_main())


if __name__ == "__main__":
    unittest.main()
