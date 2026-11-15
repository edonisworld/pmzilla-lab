"""
Tâche 2.1 (change autonomous-trains-observe) : `train_ready.py add`, sur des dépôts jetables (conception D3, D4 et D11).
Chaque refus a son test, et la liste n'est jamais écrite par un refus. Les libellés viennent de tools/train_auto_messages.py (source unique).
"""
import json
import re
import sys
import unittest
from pathlib import Path

from aide_ready import AvecAuto, RACINE

sys.path.insert(0, str(RACINE / "tools"))
import train_auto_messages  # noqa: E402


def libelle(code, langue="fr"):
    return train_auto_messages.label(code, langue)


class Ajout(AvecAuto):
    def refus(self, nom, code_raison, **args):
        r = self.pret("add", nom, "--revue", args.get("revue", "faite"))
        self.assertEqual(r.code, 3, r.texte)
        self.assertIn(f"train_ready : refusée : {nom} : {libelle(code_raison)}", r.texte)
        return r

    def test_inscription(self):
        self.preparer("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn(f"train_ready : inscrite : feat/x (sommet {self.t.sommet('feat/x')[:12]}, revue faite)", r.sortie)
        lignes = self.fichier_liste().read_text(encoding="utf-8").splitlines()
        self.assertEqual(lignes[0], "# pmzilla-train-pretes format 1")
        champs = lignes[1].split("\t")
        self.assertEqual(champs[:4], ["feat/x", self.t.sommet("feat/x"), self.t.arbre("feat/x"), "faite"])
        self.assertRegex(champs[4], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(len(lignes), 2)

    def test_inscription_en_anglais(self):
        self.preparer("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite", langue="en")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_ready: added: feat/x", r.sortie)

    def test_refus_sans_worktree(self):
        self.t.branche("feat/n", worktree=False)
        self.refus("feat/n", "sans-worktree")
        self.assertIsNone(self.octets_liste())

    def test_refus_worktree_pas_propre(self):
        self.preparer("feat/x")
        (self.t.dossier_worktree("feat/x") / "tools" / "brouillon.txt").write_text("x\n", encoding="utf-8")
        self.refus("feat/x", "worktree-sale")
        self.assertIsNone(self.octets_liste())

    def test_refus_sans_empreinte(self):
        self.t.branche("feat/x")
        self.refus("feat/x", "sans-empreinte")
        self.assertIsNone(self.octets_liste())

    def test_refus_empreinte_differente_de_l_arbre(self):
        self.t.branche("feat/x")
        self.ecrire_empreinte("feat/x", arbre=self.t.arbre("main"))
        self.refus("feat/x", "empreinte")
        self.assertIsNone(self.octets_liste())

    def test_refus_empreinte_perimee_apres_un_commit(self):
        self.preparer("feat/x")
        self.commit_dans("feat/x", {"tools/autre.sh": "a\n"})
        self.refus("feat/x", "empreinte")

    def test_refus_deja_dans_origin_main(self):
        self.t.git("branch", "feat/deja", "main")
        r = self.pret("add", "feat/deja", "--revue", "faite")
        self.assertEqual(r.code, 3, r.texte)
        self.assertIn(f"train_ready : refusée : feat/deja : {libelle('deja-fusionnee')}", r.texte)

    def test_refus_branche_introuvable(self):
        self.refus("feat/fantome", "branche-absente")

    def test_refus_branche_non_controlable(self):
        self.preparer("spike/x")
        self.refus("spike/x", "controle-impossible")

    def test_refus_outillage_protege_nomme_la_fin_de_l_auteur(self):
        self.preparer("feat/x", {"tools/finish_branch.sh": "changé\n"})
        r = self.refus("feat/x", "outillage-protege", revue="non-requise")
        # Libellé changé par R-20261101-61 et la décision D16 d'autonomous-trains-merge (tâche 9.5) : « fin de l'auteur » devient « train de l'auteur ».
        self.assertIn("train de l'auteur", r.texte)
        self.assertIsNone(self.octets_liste())

    def test_refus_postures(self):
        self.preparer("feat/x", {"CLAUDE.md": "changé\n"})
        self.refus("feat/x", "postures", revue="non-requise")

    def test_refus_base(self):
        self.preparer("feat/x", {"db/002.sql": "SELECT 2;\n"})
        self.refus("feat/x", "base", revue="non-requise")

    def test_refus_front(self):
        self.poser_liste_front("mothra/front/\n")
        self.preparer("feat/x", {"mothra/front/page.js": "x\n"})
        self.refus("feat/x", "front", revue="non-requise")

    # R-20261031-21 : avec --revue faite, les motifs d'exclusion du job n'empêchent plus l'inscription ; avec --revue non-requise ils refusent.
    def test_revue_faite_admet_une_branche_qui_touche_la_base(self):
        self.preparer("feat/x", {"db/002.sql": "SELECT 2;\n"})
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("revue faite)", r.sortie)
        self.assertEqual(self.fichier_liste().read_text(encoding="utf-8").splitlines()[1].split("\t")[:4],
                         ["feat/x", self.t.sommet("feat/x"), self.t.arbre("feat/x"), "faite"])

    def test_revue_faite_admet_une_branche_qui_touche_l_interface(self):
        self.poser_liste_front("mothra/front/\n")
        self.preparer("feat/x", {"mothra/front/page.js": "x\n"})
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("revue faite)", r.sortie)

    def test_revue_faite_admet_outillage_protege_et_postures(self):
        self.preparer("feat/x", {"tools/finish_branch.sh": "changé\n"})
        self.preparer("feat/y", {"CLAUDE.md": "changé\n"})
        for nom in ("feat/x", "feat/y"):
            r = self.pret("add", nom, "--revue", "faite")
            self.assertEqual(r.code, 0, r.texte)

    def test_revue_non_requise_refuse_toujours_la_base(self):
        self.preparer("feat/x", {"db/002.sql": "SELECT 2;\n"})
        self.refus("feat/x", "base", revue="non-requise")
        self.assertIsNone(self.octets_liste())

    def test_revue_non_requise_refuse_toujours_l_interface(self):
        self.poser_liste_front("mothra/front/\n")
        self.preparer("feat/x", {"mothra/front/page.js": "x\n"})
        self.refus("feat/x", "front", revue="non-requise")
        self.assertIsNone(self.octets_liste())

    def test_revue_faite_ne_leve_pas_le_controle_impossible(self):
        self.preparer("spike/x", {"db/002.sql": "SELECT 2;\n"})
        self.refus("spike/x", "controle-impossible")

    def test_la_ligne_admise_d_une_branche_exclue_reste_ecartee_par_check_line(self):
        # Réécrit sur D16 (autonomous-trains-merge, tâche 9.5, R-20261101-61, R-20261107-4 Q2) : la base avec la revue `faite` n'est plus exclue ; ce sont l'outillage de fin
        # et les postures (le train de l'auteur, D2) que check_line écarte encore.
        self.preparer("feat/x", {"tools/finish_branch.sh": "changé\n"})
        self.assertEqual(self.pret("add", "feat/x", "--revue", "faite").code, 0)
        r = self.pret("list", "--json")
        self.assertEqual(r.code, 0, r.texte)
        ligne = json.loads(r.sortie)["lignes"][0]
        self.assertFalse(ligne["valide"])
        self.assertEqual(ligne["raison"], "outillage-protege")

    def test_la_ligne_faite_d_une_branche_de_base_est_valide_d_apres_check_line(self):
        # D16 : la base avec la revue `faite` n'est plus une exclusion (nouveau test, jumeau du précédent).
        self.preparer("feat/x", {"db/002.sql": "SELECT 2;\n"})
        self.assertEqual(self.pret("add", "feat/x", "--revue", "faite").code, 0)
        r = self.pret("list", "--json")
        self.assertEqual(r.code, 0, r.texte)
        self.assertTrue(json.loads(r.sortie)["lignes"][0]["valide"])

    def test_refus_revue_non_requise_pour_du_code(self):
        self.preparer("feat/x")
        self.refus("feat/x", "revue", revue="non-requise")
        self.assertIsNone(self.octets_liste())

    def test_revue_non_requise_acceptee_pour_la_specification(self):
        self.preparer("chore/spec-r1", {"openspec/changes/nouveau-change/proposal.md": "p\n"})
        r = self.pret("add", "chore/spec-r1", "--revue", "non-requise")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("revue non requise)", r.sortie)

    def test_refus_liste_pleine_au_plafond(self):
        for k in range(5):
            self.inscrire(f"feat/p{k}")
        avant = self.octets_liste()
        self.preparer("feat/de-trop")
        self.refus("feat/de-trop", "liste-pleine")
        self.assertEqual(self.octets_liste(), avant)

    def test_plafond_ne_bloque_pas_la_reinscription_d_une_branche_listee(self):
        for k in range(5):
            self.inscrire(f"feat/p{k}")
        self.commit_dans("feat/p0", {"tools/plus.sh": "p\n"})
        self.ecrire_empreinte("feat/p0")
        r = self.pret("add", "feat/p0", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)

    def test_toutes_les_raisons_sont_listees_et_rien_n_est_ecrit(self):
        self.t.branche("feat/x", {"tools/finish_branch.sh": "changé\n"})   # sans empreinte, protégé
        r = self.pret("add", "feat/x", "--revue", "non-requise")
        self.assertEqual(r.code, 3, r.texte)
        for code in ("sans-empreinte", "outillage-protege", "revue"):
            self.assertIn(f"train_ready : refusée : feat/x : {libelle(code)}", r.texte)
        self.assertIsNone(self.octets_liste())

    def test_un_sommet_ou_une_empreinte_en_ligne_de_commande_est_refuse_en_usage(self):
        self.preparer("feat/x")
        for option in ("--tip", "--sommet", "--empreinte", "--fingerprint"):
            r = self.pret("add", "feat/x", "--revue", "faite", option, "0" * 40)
            self.assertEqual(r.code, 2, f"{option} : {r.texte}")
        r = self.pret("add", "feat/x", "--revue", "faite", "0" * 40)
        self.assertEqual(r.code, 2, r.texte)
        self.assertIsNone(self.octets_liste())

    def test_la_revue_est_obligatoire(self):
        self.preparer("feat/x")
        self.assertEqual(self.pret("add", "feat/x").code, 2)
        self.assertEqual(self.pret("add", "feat/x", "--revue", "peut-etre").code, 2)

    def test_reinscription_garde_la_position_et_la_ligne_unique(self):
        self.inscrire("feat/x")
        self.inscrire("feat/y")
        self.commit_dans("feat/x", {"tools/suite.sh": "s\n"})
        self.ecrire_empreinte("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        lignes = self.fichier_liste().read_text(encoding="utf-8").splitlines()[1:]
        self.assertEqual([l.split("\t")[0] for l in lignes], ["feat/x", "feat/y"])
        self.assertEqual(lignes[0].split("\t")[1], self.t.sommet("feat/x"))

    def test_add_lance_prune_d_abord(self):
        self.inscrire("feat/x")
        # la branche est fusionnée dans origin/main : sa ligne disparaît au prochain add
        sommet = self.t.sommet("feat/x")
        self.t.git("update-ref", "refs/remotes/origin/main", sommet)
        self.preparer("feat/y")
        r = self.pret("add", "feat/y", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("1 ligne(s) retirée(s) (fusionnées ou disparues)", r.sortie)
        noms = [l.split("\t")[0] for l in self.fichier_liste().read_text(encoding="utf-8").splitlines()[1:]]
        self.assertEqual(noms, ["feat/y"])


if __name__ == "__main__":
    unittest.main()
