"""
Groupe 3.3 (change targeted-suites-admission, design D4) : la preuve d'un sommet pour `train_ready.py add` et `list --json`, sur des dépôts jetables.
La preuve est l'empreinte du runner complet, sinon l'empreinte de branche (`run_all.sh --branch`), jamais l'empreinte ciblée par commit ; une seule
fonction (`proof_of`). Vrais enfants : l'outil, Git ; aucun faux de ce test (les faux de l'aide sont ceux de tests/train_auto/aide_auto.py).
"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from aide_ready import AvecAuto, RACINE

sys.path.insert(0, str(RACINE / "tools"))
import train_auto_messages  # noqa: E402
import train_ready  # noqa: E402


class Preuve(AvecAuto):
    def fichier_empreinte(self, nom, fichier):
        wt = self.t.dossier_worktree(nom)
        return Path(self.t.git("rev-parse", "--path-format=absolute", "--git-path", fichier, cwd=wt))

    def arbre_du_sommet(self, nom):
        return self.t.git("rev-parse", "HEAD^{tree}", cwd=self.t.dossier_worktree(nom))

    def ecrire_branche(self, nom, arbre=None, suites="alpha,beta"):
        self.fichier_empreinte(nom, "pmzilla-run-branch-ok").write_text(f"{arbre or self.arbre_du_sommet(nom)}\t{suites}\n", encoding="utf-8")

    def ecrire_ciblee(self, nom):
        self.fichier_empreinte(nom, "pmzilla-run-targeted-ok").write_text(self.arbre_du_sommet(nom) + "\n", encoding="utf-8")

    def refus(self, nom, code_raison):
        r = self.pret("add", nom, "--revue", "faite")
        self.assertEqual(r.code, 3, r.texte)
        self.assertIn(f"train_ready : refusée : {nom} : {train_auto_messages.label(code_raison, 'fr')}", r.texte)
        self.assertIsNone(self.octets_liste())

    def lignes_json(self):
        r = self.pret("list", "--json")
        self.assertEqual(r.code, 0, r.texte)
        return json.loads(r.sortie)["lignes"]

    def test_inscription_avec_l_empreinte_de_branche(self):
        self.t.branche("feat/x")
        self.ecrire_branche("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        lignes = r.sortie.splitlines()
        self.assertEqual(lignes[-2], f"train_ready : inscrite : feat/x (sommet {self.t.sommet('feat/x')[:12]}, revue faite)")
        self.assertEqual(lignes[-1], "train_ready : preuve : suites de la branche (2)")

    def test_inscription_avec_l_empreinte_complete(self):
        self.preparer("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(r.sortie.splitlines()[-1], "train_ready : preuve : runner complet")

    def test_l_empreinte_ciblee_par_commit_seule_est_refusee(self):
        self.t.branche("feat/x")
        self.ecrire_ciblee("feat/x")
        self.refus("feat/x", "sans-empreinte")

    def test_empreinte_de_branche_perimee_refusee_comme_empreinte_differente(self):
        self.t.branche("feat/x")
        self.ecrire_branche("feat/x", arbre=self.t.arbre("main"))
        self.refus("feat/x", "empreinte")

    def test_empreinte_de_branche_perimee_apres_un_commit(self):
        self.t.branche("feat/x")
        self.ecrire_branche("feat/x")
        self.commit_dans("feat/x", {"tools/autre.sh": "a\n"})
        self.refus("feat/x", "empreinte")

    def test_empreinte_de_branche_mal_formee_n_est_pas_une_preuve(self):
        self.t.branche("feat/x")
        self.fichier_empreinte("feat/x", "pmzilla-run-branch-ok").write_text("pas-un-arbre\n", encoding="utf-8")
        self.refus("feat/x", "sans-empreinte")

    def test_libelles_de_sans_empreinte(self):
        self.assertEqual(train_auto_messages.label("sans-empreinte", "fr"), "aucune preuve dans le worktree (runner complet ou --branch)")
        self.assertEqual(train_auto_messages.label("sans-empreinte", "en"), "no proof in the worktree (complete runner or --branch)")

    def test_json_d_une_ligne_prouvee_par_la_branche(self):
        self.t.branche("feat/x")
        self.ecrire_branche("feat/x", suites="alpha,beta")
        self.assertEqual(self.pret("add", "feat/x", "--revue", "faite").code, 0)
        ligne = self.lignes_json()[0]
        self.assertEqual((ligne["preuve"], ligne["suites"], ligne["valide"]), ("ciblee", ["alpha", "beta"], True))

    def test_json_d_une_ligne_prouvee_par_le_runner_complet(self):
        self.inscrire("feat/x")
        ligne = self.lignes_json()[0]
        self.assertEqual((ligne["preuve"], ligne["suites"]), ("complete", []))

    def test_la_preuve_complete_est_preferee(self):
        self.preparer("feat/x")
        self.ecrire_branche("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(r.sortie.splitlines()[-1], "train_ready : preuve : runner complet")
        self.assertEqual(self.lignes_json()[0]["preuve"], "complete")

    def test_la_ligne_de_preuve_de_add_est_celle_de_l_evaluation_sans_recalcul(self):
        # revue 2026-10-31, point 5 : une empreinte complète qui apparaît après l'évaluation (course avec un autre lancement) ne change pas la ligne imprimée
        self.t.branche("feat/x")
        self.ecrire_branche("feat/x", suites="alpha,beta")
        reel = train_ready.evaluate_add

        def evaluer_puis_changer_la_preuve(*args, **kw):
            resultat = reel(*args, **kw)
            self.fichier_empreinte("feat/x", "pmzilla-run-all-ok").write_text(self.arbre_du_sommet("feat/x") + "\n", encoding="utf-8")
            return resultat

        sortie = io.StringIO()
        with mock.patch.object(train_ready, "evaluate_add", evaluer_puis_changer_la_preuve), \
             mock.patch.object(train_ready, "workspace", lambda: self.t.contenu), \
             mock.patch.object(train_ready.lab_paths, "run_tree", lambda ws: self.t.run), \
             mock.patch.object(train_ready, "data_dir", lambda: self.dossier_train()), \
             contextlib.redirect_stdout(sortie):
            code = train_ready.main(["add", "feat/x", "--revue", "faite"])
        self.assertEqual(code, 0)
        self.assertEqual(sortie.getvalue().splitlines()[-1], "train_ready : preuve : suites de la branche (2)")

    def test_le_format_de_la_liste_ne_change_pas(self):
        self.t.branche("feat/x")
        self.ecrire_branche("feat/x")
        self.assertEqual(self.pret("add", "feat/x", "--revue", "faite").code, 0)
        champs = self.fichier_liste().read_text(encoding="utf-8").splitlines()[1].split("\t")
        self.assertEqual(len(champs), 5)
        self.assertEqual(champs[2], self.t.arbre("feat/x"))


if __name__ == "__main__":
    unittest.main()
