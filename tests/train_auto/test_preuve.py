"""
Groupe 3.4 (change targeted-suites-admission, design D4) : `train_auto.check_line` accepte la preuve du runner complet ou l'empreinte de branche du
sommet (une seule fonction, `train_ready.proof_of`), et écarte une ligne dont l'empreinte de branche a disparu ou n'est plus celle de l'arbre.
Faux déclaré : le faux lsof de la carte des processus n'est pas posé ici ; risque non couvert : aucun (le contrôle des lignes ne le lit pas).
"""
import sys
import unittest
from pathlib import Path

from aide_auto import AvecAuto, RACINE

sys.path.insert(0, str(RACINE / "tools"))
import train_auto_messages  # noqa: E402


def libelle(code):
    return train_auto_messages.label(code, "fr")


class PreuveDesLignes(AvecAuto):
    def fichier_empreinte(self, nom, fichier):
        return Path(self.t.git("rev-parse", "--path-format=absolute", "--git-path", fichier, cwd=self.t.dossier_worktree(nom)))

    def ecrire_branche(self, nom, arbre=None, suites="alpha"):
        arbre = arbre or self.t.git("rev-parse", "HEAD^{tree}", cwd=self.t.dossier_worktree(nom))
        self.fichier_empreinte(nom, "pmzilla-run-branch-ok").write_text(f"{arbre}\t{suites}\n", encoding="utf-8")

    def inscrire_par_la_branche(self, nom):
        self.t.branche(nom)
        self.ecrire_branche(nom)
        r = self.pret("add", nom, "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)

    def test_ligne_prouvee_par_l_empreinte_de_branche_est_retenue(self):
        self.inscrire_par_la_branche("feat/x")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual([b["branche"] for b in self.dernier()["retenues"]], ["feat/x"])
        self.assertEqual(self.dernier()["ecartees"], [])

    def test_ligne_prouvee_par_le_runner_complet_est_retenue(self):
        self.inscrire("feat/x")
        self.assertEqual([b["branche"] for b in (self.passage(), self.dernier())[1]["retenues"]], ["feat/x"])

    def test_empreinte_de_branche_effacee_ecarte_la_ligne_sans_empreinte(self):
        self.inscrire_par_la_branche("feat/x")
        self.fichier_empreinte("feat/x", "pmzilla-run-branch-ok").unlink()   # un nouveau lancement de branche rouge l'a effacée
        r = self.passage()
        self.assertIn(f"train_auto : écartée : feat/x : {libelle('sans-empreinte')}", r.sortie)
        self.assertEqual([e["raison"] for e in self.dernier()["ecartees"]], ["sans-empreinte"])

    def test_empreinte_de_branche_d_un_autre_arbre_ecarte_la_ligne_empreinte(self):
        self.inscrire_par_la_branche("feat/x")
        self.ecrire_branche("feat/x", arbre=self.t.arbre("main"))
        r = self.passage()
        self.assertIn(f"train_auto : écartée : feat/x : {libelle('empreinte')}", r.sortie)

    def test_empreinte_ciblee_par_commit_ne_prouve_rien(self):
        self.inscrire_par_la_branche("feat/x")
        self.fichier_empreinte("feat/x", "pmzilla-run-branch-ok").unlink()
        self.fichier_empreinte("feat/x", "pmzilla-run-targeted-ok").write_text(self.t.arbre("feat/x") + "\n", encoding="utf-8")
        r = self.passage()
        self.assertIn(f"train_auto : écartée : feat/x : {libelle('sans-empreinte')}", r.sortie)


if __name__ == "__main__":
    unittest.main()
