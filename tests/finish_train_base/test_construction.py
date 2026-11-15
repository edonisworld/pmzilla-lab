"""
Tâche 2.6 (change finish-train-v1) : la construction du train par le script (conception D7, code 64). Les commits qui atteignent main sont les siens :
fusions pures, construites par git merge-tree et git commit-tree, sous l'identité de l'auteur, sans aucune référence écrite pendant la construction.
"""
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, NOM_FICTIF  # noqa: E402


class Forme(AvecTrain):
    def trois(self):
        self.t.branche("feat/a", {"tools/a.sh": "a\n"})
        self.t.branche("feat/b", {"tools/b.sh": "b\n"})
        self.t.branche("feat/c", {"tools/c.sh": "c\n"})
        return ["feat/a", "feat/b", "feat/c"]

    def entetes(self, commit):
        brut = self.t.git("cat-file", "commit", commit)
        tete, _, corps = brut.partition("\n\n")
        return tete.splitlines(), corps

    def test_forme_d_un_train_de_trois_branches(self):
        noms = self.trois()
        base = self.t.origin_main()
        r = self.t.lance("--essai", *noms)
        self.assertEqual(r.code, 0, r.texte)
        sommet = self.sommet_du_train(r)
        chaine = self.t.chaine_premiers_parents(sommet, base)
        self.assertEqual(len(chaine), 3)
        for k, commit in enumerate(chaine):
            parents = self.t.git("rev-list", "--parents", "-n", "1", commit).split()[1:]
            self.assertEqual(len(parents), 2, "exactement deux parents")
            self.assertEqual(parents[0], base if k == 0 else chaine[k - 1], "premier parent")
            self.assertEqual(parents[1], self.t.sommet(noms[k]), "second parent : le sommet de la branche")
            entetes, message = self.entetes(commit)
            self.assertEqual(message, f"Merge branch '{noms[k]}'")
            self.assertEqual(sorted(l.split()[0] for l in entetes), ["author", "committer", "parent", "parent", "tree"])
            auteur = [l for l in entetes if l.startswith("author ")][0]
            commiteur = [l for l in entetes if l.startswith("committer ")][0]
            self.assertTrue(auteur.startswith("author test <t@example.org> "), auteur)
            self.assertTrue(commiteur.startswith("committer test <t@example.org> "), commiteur)
            arbre = self.t.git("merge-tree", "--write-tree", parents[0], parents[1]).splitlines()[0]
            self.assertEqual(self.t.arbre(commit), arbre, "l'arbre est celui de merge-tree des deux parents")
        # le dernier commit de la chaîne est le sommet du train : « train construit : sommet … »
        self.assertEqual(chaine[-1], sommet)

    def test_le_message_se_termine_par_un_seul_retour_a_la_ligne(self):
        noms = self.trois()
        r = self.t.lance("--essai", *noms)
        sommet = self.sommet_du_train(r)
        brut = self.t.git("cat-file", "commit", sommet) + "\n"
        self.assertTrue(brut.endswith(f"Merge branch '{noms[-1]}'\n"))
        self.assertFalse(brut.endswith("\n\n"))

    def test_le_train_n_est_reference_par_aucune_reference_et_aucun_worktree(self):
        noms = self.trois()
        avant = self.t.instantane()
        r = self.t.lance("--essai", *noms)
        self.assertEqual(r.code, 0, r.texte)
        self.rien_ne_change(avant)
        sommet = self.sommet_du_train(r)
        self.assertEqual(self.t.git("branch", "-a", "--contains", sommet), "")
        self.assertEqual(self.t.git("tag", "--contains", sommet), "")
        self.assertEqual(self.t.git("for-each-ref", "refs/heads/lot"), "")

    def test_aucune_reference_ecrite_pendant_la_construction_et_le_sommet_tenu_par_le_worktree_d_integration(self):
        noms = self.trois()
        avant = sorted(self.t.git("for-each-ref", "--format=%(refname)", "refs/heads").splitlines())
        r = self.t.lance(*noms, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        pendant = sorted((self.t.etat / "runner-refs.txt").read_text(encoding="utf-8").splitlines())
        self.assertEqual(pendant, avant)
        head = (self.t.etat / "runner-head.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(head[:12], self.sommet_du_train(r)[:12], "le worktree d'intégration est détaché sur le sommet du train")
        # le passage du conteneur est lancé avant la passe Mac, sans rejeu, sans écrire aucune référence (il ne touche pas le worktree d'intégration)
        ci = (self.t.etat / "ci-appels").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(ci), 1)
        self.assertNotIn("--rejeu", ci[0])

    def test_la_ligne_du_train_puis_le_train_construit(self):
        noms = self.trois()
        base = self.t.origin_main()
        r = self.t.lance("--essai", *noms)
        self.contient(r, f"train : 3 branche(s), base origin/main {base[:12]}", "train construit : sommet ")


class Conflit(AvecTrain):
    def test_conflit_entre_deux_branches(self):
        self.t.branche("feat/a", {"tools/outil.sh": "version a\n"})
        self.t.branche("feat/b", {"tools/outil.sh": "version b\n"})
        avant = self.t.instantane()
        r = self.t.lance("feat/a", "feat/b")
        self.code(r, 64, "conflit à la construction du train : feat/b avec feat/a sur 1 fichier(s) ; rien n'est fusionné",
                  f"ligne sans cette branche : {self.t.ligne} feat/a")
        self.contient(r, "tools/outil.sh")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])
        self.assertFalse((self.t.etat / "ci-appels").exists(), "le passage du conteneur n'est pas lancé sur un train qui n'a pas pu être construit")

    def test_la_ligne_de_relance_du_64_protege_les_noms_par_printf_q(self):
        self.t.branche("feat/a&b", {"tools/a.sh": "a\n"})
        self.t.branche("feat/c", {"tools/outil.sh": "version c\n"})
        self.t.branche("feat/b", {"tools/outil.sh": "version b\n"})
        r = self.t.lance("feat/a&b", "feat/c", "feat/b")
        self.code(r, 64, f"ligne sans cette branche : {self.t.ligne} feat/a\\&b feat/c")

    def test_conflit_avec_trois_branches_nomme_la_branche_fautive(self):
        self.t.branche("feat/a", {"tools/a.sh": "a\n"})
        self.t.branche("feat/c", {"tools/outil.sh": "version c\n"})
        self.t.branche("feat/b", {"tools/outil.sh": "version b\n"})
        r = self.t.lance("feat/a", "feat/c", "feat/b")
        self.code(r, 64, "conflit à la construction du train : feat/b avec ")
        self.contient(r, f"ligne sans cette branche : {self.t.ligne} feat/a feat/c")

    def test_erreur_de_merge_tree_au_dela_de_un_ne_blame_aucune_branche(self):
        self.t.branche("feat/a", {"tools/a.sh": "a\n"})
        self.t.branche("feat/b", {"tools/b.sh": "b\n"})
        avant = self.t.instantane()
        r = self.t.lance("feat/a", "feat/b", extra={"FAKE_MERGE_TREE_CODE": "128"})
        self.code(r, 64, "construction du train impossible (git merge-tree, code 128) ; rien n'est fusionné")
        self.absent(r, "conflit à la construction", "ligne sans cette branche")
        self.rien_ne_change(avant)


NOM_TORDU = 'tools/a b"c\nd.txt'   # une espace, un guillemet et un retour à la ligne


class CheminsEnConflit(AvecTrain):
    """Décision de l'auteur du 2026-10-27 (D7, tâche 2.17) : merge-tree est lu en -z, champ par champ ; chaque chemin est affiché sur une ligne, entre
    guillemets à la manière de Git quand il porte un retour à la ligne, une tabulation, un guillemet ou une barre inverse."""

    def test_conflit_sur_un_nom_avec_espace_guillemet_et_retour_a_la_ligne(self):
        self.t.branche("feat/a", {NOM_TORDU: "version a\n"})
        self.t.branche("feat/b", {NOM_TORDU: "version b\n"})
        avant = self.t.instantane()
        r = self.t.lance("feat/a", "feat/b")
        self.code(r, 64, "conflit à la construction du train : feat/b avec feat/a sur 1 fichier(s) ; rien n'est fusionné")
        lignes = r.texte.splitlines()
        i = lignes.index("finish_train : conflit à la construction du train : feat/b avec feat/a sur 1 fichier(s) ; rien n'est fusionné")
        self.assertEqual(lignes[i + 1], '"tools/a b\\"c\\nd.txt"', "le chemin tient sur une seule ligne, cité à la manière de Git")
        self.assertEqual(lignes[i + 2], f"finish_train : ligne sans cette branche : {self.t.ligne} feat/a", "aucune ligne en plus")
        self.rien_ne_change(avant)

    def test_un_chemin_ordinaire_n_est_pas_cite(self):
        self.t.branche("feat/a", {"tools/a b.txt": "version a\n"})
        self.t.branche("feat/b", {"tools/a b.txt": "version b\n"})
        r = self.t.lance("feat/a", "feat/b")
        self.assertEqual(r.code, 64, r.texte)
        self.assertIn("\ntools/a b.txt\n", r.texte)

    def test_une_branche_qui_ajoute_un_tel_fichier_sans_conflit(self):
        self.t.branche("feat/a", {NOM_TORDU: "contenu\n"})
        base = self.t.origin_main()
        r = self.t.lance("--essai", "feat/a")
        self.assertEqual(r.code, 0, r.texte)
        sommet = self.sommet_du_train(r)
        arbre = self.t.git("merge-tree", "--write-tree", base, self.t.sommet("feat/a")).splitlines()[0]
        self.assertEqual(self.t.arbre(sommet), arbre, "l'arbre du train est celui de merge-tree de ses deux parents")
        self.assertEqual(self.arbre_du_train(r), arbre[:12])

    def test_le_controle_des_noms_passe_avant_l_affichage_des_chemins_en_conflit(self):
        # revue de u5, m-12 : un nom sensible dans un chemin en conflit ne sort jamais sur l'écran ni au journal
        chemin = f"tools/{NOM_FICTIF}.txt"
        self.t.branche("feat/a", {chemin: "version a\n"})
        self.t.branche("feat/b", {chemin: "version b\n"})
        r = self.t.lance("feat/a", "feat/b")
        self.assertEqual(r.code, 65, r.texte)
        self.absent(r, NOM_FICTIF, "conflit à la construction")
        self.assertNotIn(NOM_FICTIF, self.t.log())


if __name__ == "__main__":
    unittest.main()
