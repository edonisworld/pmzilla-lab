"""
autonomous-trains-merge, tranche 2 (design D18 point 1, tâche 6.1) : sur un vrai lancement du train dans le dépôt jetable, le train écrit dans son
verrou, sous son jeton et avant toute construction, le fichier `gel` : une ligne `B` par branche, une ligne `W` par worktree de ces branches, la ligne
`W` du worktree d'intégration `wt-train-*`, puis `fin`. Le verrou n'existe que le temps du train : le contenu est copié par deux faux, la garde du
matin (qui précède l'état des références et la construction) et le faux ci_local (qui tourne dans le worktree d'intégration).

Faux déclarés (aide_train.py) : la passe Mac, ci_local et la garde du matin. Le script de fin, le module du verrou et Git sont les vrais.
"""
import os
import unittest

from aide_train import AvecTrain


class GelCibleEcritParLeTrain(AvecTrain):
    def lancer_avec_copies(self, *noms):
        lock = self.t.commun() / "pmzilla-fin-en-cours"
        self.copie_matin = self.t.etat / "gel-matin.txt"
        self.copie_ci = self.t.etat / "gel-ci.txt"
        extra = {"FINISH_TRAIN_MORNING_CHECK": f'cp "{lock}/gel" "{self.copie_matin}"; bash {self.t.matin}',
                 "FINISH_TRAIN_CI": f'cp "{lock}/gel" "{self.copie_ci}"; bash {self.t.ci}'}
        return self.t.lance(*noms, extra=extra, entree="o\n")

    def test_la_liste_gel_porte_les_branches_leurs_worktrees_et_le_worktree_d_integration(self):
        self.t.branche("feat/x")
        self.t.branche("feat/y")
        r = self.lancer_avec_copies("feat/x", "feat/y")
        self.assertEqual(r.code, 0, r.texte)
        self.assertTrue(self.copie_matin.exists(), "la liste est déjà dans le verrou quand la garde du matin tourne (avant la base et la construction)")
        lignes = self.copie_matin.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lignes[:4], ["B feat/x", f"W {self.t.dossier_worktree('feat/x')}", "B feat/y", f"W {self.t.dossier_worktree('feat/y')}"])
        self.assertEqual(lignes[-1], "fin")
        integration = [l for l in lignes if l.startswith("W ") and os.path.basename(l[2:]).startswith("wt-train-")]
        self.assertEqual(len(integration), 1, lignes)
        self.assertEqual(os.path.dirname(integration[0][2:]), str(self.t.worktrees))
        self.assertEqual(len(lignes), 6, lignes)

    def test_le_worktree_d_integration_nomme_dans_la_liste_est_celui_du_train(self):
        self.t.branche("feat/x")
        r = self.lancer_avec_copies("feat/x")
        self.assertEqual(r.code, 0, r.texte)
        integration = [l[2:] for l in self.copie_matin.read_text(encoding="utf-8").splitlines() if "wt-train-" in l]
        self.assertEqual(len(integration), 1)
        self.assertTrue(self.copie_ci.exists(), "le faux ci_local a tourné dans le worktree d'intégration")
        self.assertEqual(self.copie_ci.read_text(encoding="utf-8"), self.copie_matin.read_text(encoding="utf-8"), "la liste ne change pas pendant le train")
        self.assertIn(f"worktree retiré : {integration[0]}", r.texte, "le worktree nommé dans la liste est bien celui que le train a créé puis retiré")

    def test_une_branche_sans_worktree_est_listee_sans_ligne_w(self):
        self.t.branche("feat/x", worktree=False)
        r = self.lancer_avec_copies("feat/x")
        self.assertEqual(r.code, 0, r.texte)
        lignes = self.copie_matin.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lignes[0], "B feat/x")
        self.assertEqual([l for l in lignes if l.startswith("W ")], [l for l in lignes if "wt-train-" in l])

    def test_le_verrou_est_retire_avec_sa_liste_a_la_fin_du_train(self):
        self.t.branche("feat/x")
        r = self.lancer_avec_copies("feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists())


if __name__ == "__main__":
    unittest.main()
