"""
R-20261102-43 : un train admet jusqu'à 3 branches juges (outillage protégé de classe `juge`) quand deux branches ne touchent jamais le même fichier juge ;
les paires fusionnent sans conflit (la construction du train le vérifie). .claude/ et un CLAUDE.md restent refusés dès que le train a plus d'une branche.
Remplace : « une branche juge passe seule » (tests/finish_train/test_admission.py, test_admission_classes.py, test_une_branche.py) ; retrait : permanent
tant que le train porte des branches juges. La liste protégée fictive du harnais (aide_train.LISTE_PROTEGEE) ne porte aucune étiquette : ses motifs valent `juge`.
"""
import re
import unittest
from pathlib import Path

from aide_train import AvecTrain

RACINE = Path(__file__).resolve().parents[2]
RUNNER_ET_PREUVE = ("tests/run_all.sh", "ci/passage.sh", "tools/preuve_arbre.py", "tools/finish_train.sh")


class RunnerEtPreuveDansLaVraieListe(unittest.TestCase):
    """R-20261102-55 (4) : les quatre fichiers du runner et de la preuve sont de classe `juge` dans tools/finish_protected.txt (sinon la règle
    « reste seule dans son train » ne les verrait pas : elle lit les fichiers juges de la branche), et finish_train.sh les nomme tous les quatre."""

    def test_les_quatre_fichiers_du_runner_et_de_la_preuve_sont_juges_dans_la_vraie_liste(self):
        motifs = []
        for ligne in (RACINE / "tools" / "finish_protected.txt").read_text(encoding="utf-8").splitlines():
            if ligne.startswith("#") or "#[juge]" not in ligne:
                continue
            motifs.append(ligne.split("#", 1)[0].strip())
        for chemin in RUNNER_ET_PREUVE:
            self.assertTrue(any(m == chemin or (m.endswith("/") and chemin.startswith(m)) for m in motifs), chemin)

    def test_le_script_nomme_les_quatre_fichiers(self):
        # réécrit (R-20261106-32, option A) : les quatre chemins sont dans la liste unique, et le train lit le champ du JSON de finish_checks
        liste = [l.split("#", 1)[0].strip() for l in (RACINE / "tools" / "finish_runner_paths.txt").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sorted(l for l in liste if l), sorted(RUNNER_ET_PREUVE))
        texte = (RACINE / "tools" / "finish_train.sh").read_text(encoding="utf-8")
        code = [l for l in texte.splitlines() if not l.lstrip().startswith("#")]
        # revue Opus 4.1, constat 3 : le lecteur du champ, et les deux lignes qui l'emploient, hors commentaire
        self.assertTrue(any('"runner_proof_touched": \\[' in l for l in code), "lecteur json_runner absent")
        self.assertTrue(any('RUNF=$(json_runner "$out")' in l for l in code))
        self.assertTrue(any('elif [ "${#NAMES[@]}" -gt 1 ] && [ -n "$RUNF" ]' in l for l in code))

    def test_aucun_des_quatre_chemins_en_litteral_hors_commentaire(self):
        # tâche 3.3 (b), D3 : le train ne recopie plus la liste. Les seuls emplois admis sont quatre formes exactes, chacune avec son compte exact (revue Opus 4.1, constat 2) :
        # la ligne de commande du train (l.160, l.429) et le runner Mac (l.1164, l.1181).
        invocations = {'LIGNE="bash tools/finish_train.sh"': 1, 'LIGNE="bash $run/tools/finish_train.sh"': 1,
                       "${FINISH_TRAIN_RUNNER:-bash tests/run_all.sh --mac}": 1, "${FINISH_TRAIN_RUNNER:-bash tests/run_all.sh}": 1}
        lignes = [l for l in (RACINE / "tools" / "finish_train.sh").read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#")]
        for invocation, compte in invocations.items():
            self.assertEqual(sum(l.count(invocation) for l in lignes), compte, invocation)
        for numero, ligne in enumerate((RACINE / "tools" / "finish_train.sh").read_text(encoding="utf-8").splitlines(), 1):
            if ligne.lstrip().startswith("#"):
                continue
            code = ligne
            for invocation in invocations:
                code = code.replace(invocation, "")
            for chemin in RUNNER_ET_PREUVE:
                for forme in (chemin, chemin.replace(".", "\\.")):
                    self.assertNotIn(forme, code, f"finish_train.sh ligne {numero} : {chemin} en littéral")


class PlusieursJuges(AvecTrain):
    def test_deux_branches_juges_sur_des_fichiers_differents_sont_admises(self):
        self.t.branche("feat/a", {"tools/finish_branch.sh": "a\n"})
        self.t.branche("feat/b", {"tools/hooks/b.sh": "b\n"})
        r = self.t.lance("--essai", "feat/a", "feat/b")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "branche juge de rang 1 : feat/a) : 1 fichier(s)", "      tools/finish_branch.sh",
                      "branche juge de rang 2 : feat/b) : 1 fichier(s)", "      tools/hooks/b.sh")
        self.absent(r, "train d'une seule branche")

    def test_trois_branches_juges_sur_des_fichiers_differents_sont_admises(self):
        self.t.branche("feat/a", {"tools/finish_branch.sh": "a\n"})
        self.t.branche("feat/b", {"tools/hooks/b.sh": "b\n"})
        self.t.branche("feat/c", {"tools/hooks/c.sh": "c\n"})   # tests/run_all.sh ne convient plus : une branche du runner reste seule (ajout de l'auteur à R-20261102-43)
        r = self.t.lance("--essai", "feat/a", "feat/b", "feat/c")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "branche juge de rang 3 : feat/c) : 1 fichier(s)", "      tools/hooks/c.sh")

    def test_une_branche_juge_avec_une_branche_ordinaire_est_admise(self):
        self.t.branche("feat/a", {"tools/finish_branch.sh": "a\n"})
        self.t.branche("feat/b", {"tools/outil.sh": "b\n"})
        r = self.t.lance("--essai", "feat/a", "feat/b")
        self.assertEqual(r.code, 0, r.texte)

    def test_deux_branches_juges_sur_le_meme_fichier_juge_sont_refusees(self):
        self.t.branche("feat/a", {"tools/hooks/commun.sh": "a\n"})
        self.t.branche("feat/b", {"tools/hooks/commun.sh": "b\n", "tools/hooks/autre.sh": "x\n"})
        avant = self.t.instantane()
        r = self.t.lance("feat/a", "feat/b")
        self.code(r, 62, "branche(s) refusée(s) au train : 1 sur 2 ; rien n'est fusionné", f"ligne sans les branches refusées : {self.t.ligne} feat/a")
        self.contient(r, "  - feat/b : fichier juge tools/hooks/commun.sh touché aussi par la branche de rang 1 (rang 2 ici) : deux branches juges ne passent pas ensemble")
        self.rien_ne_change(avant)

    def test_le_fichier_juge_commun_est_nomme_entre_guillemets_quand_son_nom_l_exige(self):
        self.t.branche("feat/a", {'tools/hooks/a"b.sh': "a\n"})
        self.t.branche("feat/b", {'tools/hooks/a"b.sh': "b\n"})
        r = self.t.lance("--essai", "feat/a", "feat/b")
        self.assertEqual(r.code, 62, r.texte)
        self.contient(r, r'fichier juge "tools/hooks/a\"b.sh" touché aussi par la branche de rang 1')

    def test_deux_branches_juges_sur_des_fichiers_differents_en_conflit_sur_un_fichier_ordinaire_donnent_64(self):
        # la construction, dans l'ordre de la ligne, refuse tout conflit (64) : l'admission ne le voit pas, la construction le refuse, rien n'est fusionné
        self.t.branche("feat/a", {"tools/finish_branch.sh": "a\n", "tools/outil.sh": "version a\n"})
        self.t.branche("feat/b", {"tools/hooks/b.sh": "b\n", "tools/outil.sh": "version b\n"})
        avant = self.t.instantane()
        r = self.t.lance("feat/a", "feat/b")
        self.code(r, 64, "conflit à la construction du train : feat/b avec feat/a sur 1 fichier(s) ; rien n'est fusionné",
                  f"ligne sans cette branche : {self.t.ligne} feat/a")
        self.contient(r, "tools/outil.sh")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])

    # R-20261102-43 (ajout de l'auteur) : nouvelle règle, remplace : rien ; retrait : permanent tant que le train juge son arbre avec le runner et la preuve
    # de ses propres branches. tests/run_all.sh, ci/passage.sh, tools/preuve_arbre.py et tools/finish_train.sh sont de classe `juge` dans la vraie liste.
    def test_une_branche_qui_modifie_le_runner_reste_seule_et_l_autre_branche_juge_est_admise(self):
        self.t.branche("feat/a", {"tests/run_all.sh": "#!/bin/bash\nexit 0\n"})
        self.t.branche("feat/b", {"tools/hooks/b.sh": "b\n"})
        r = self.t.lance("--essai", "feat/a", "feat/b")
        self.code(r, 62, "branche(s) refusée(s) au train : 1 sur 2 ; rien n'est fusionné", f"ligne sans les branches refusées : {self.t.ligne} feat/b")
        self.contient(r, "  - feat/a : modifie le runner ou la preuve : train d'une seule branche (R-20261102-43)", "      tests/run_all.sh")

    def test_chacun_des_fichiers_du_runner_et_de_la_preuve_de_la_liste_fictive_est_refuse_a_plusieurs(self):
        # La liste protégée fictive du harnais ne contient, parmi les quatre fichiers, que tests/run_all.sh et tools/finish_train.sh : ci/passage.sh et
        # tools/preuve_arbre.py y seraient des fichiers ordinaires. Leur classe `juge` dans la vraie liste est vérifiée par
        # test_les_quatre_fichiers_du_runner_et_de_la_preuve_sont_juges_dans_la_vraie_liste ; le motif du script les nomme tous les quatre.
        fichiers = {"feat/p1": "tests/run_all.sh", "feat/p3": "tools/finish_train.sh"}
        for nom, fichier in fichiers.items():
            self.t.branche(nom, {fichier: "x\n"})
        self.t.branche("feat/q")
        r = self.t.lance("--essai", *fichiers, "feat/q")
        self.code(r, 62, "branche(s) refusée(s) au train : 2 sur 3 ; rien n'est fusionné", f"ligne sans les branches refusées : {self.t.ligne} feat/q")
        for nom, fichier in fichiers.items():
            self.contient(r, f"  - {nom} : modifie le runner ou la preuve : train d'une seule branche (R-20261102-43)", f"      {fichier}")

    def test_la_branche_du_runner_seule_est_admise(self):
        self.t.branche("feat/a", {"tests/run_all.sh": "#!/bin/bash\nexit 0\n"})
        r = self.t.lance("--essai", "feat/a")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train d'une branche : 1 fichier(s)", "      tests/run_all.sh")

    def test_quatre_branches_juges_la_quatrieme_est_refusee(self):
        for k, nom in enumerate(("a", "b", "c", "d")):
            self.t.branche(f"feat/{nom}", {f"tools/hooks/{nom}.sh": f"{k}\n"})
        r = self.t.lance("--essai", "feat/a", "feat/b", "feat/c", "feat/d")
        self.code(r, 62, "branche(s) refusée(s) au train : 1 sur 4 ; rien n'est fusionné", f"ligne sans les branches refusées : {self.t.ligne} feat/a feat/b feat/c")
        self.contient(r, "  - feat/d : quatrième branche juge (rang 4) : au plus 3 branches juges par train")

    def test_une_branche_refusee_pour_un_autre_motif_ne_compte_pas_dans_les_trois(self):
        for nom in ("a", "b", "c", "d"):
            self.t.branche(f"feat/{nom}", {f"tools/hooks/{nom}.sh": "x\n"})
        (self.t.dossier_worktree("feat/a") / "sale.txt").write_text("x\n", encoding="utf-8")
        r = self.t.lance("--essai", "feat/a", "feat/b", "feat/c", "feat/d")
        self.code(r, 62, "branche(s) refusée(s) au train : 1 sur 4 ; rien n'est fusionné")
        self.contient(r, "  - feat/a : worktree pas propre")
        self.absent(r, "quatrième branche juge")

    def test_une_branche_claude_reste_refusee_a_plusieurs_meme_avec_une_branche_juge_admise(self):
        self.t.branche("feat/a", {"tools/finish_branch.sh": "a\n"})
        self.t.branche("feat/b", {".claude/reglage.json": "{}\n"})
        r = self.t.lance("--essai", "feat/a", "feat/b")
        self.code(r, 62, "branche(s) refusée(s) au train : 1 sur 2 ; rien n'est fusionné", f"ligne sans les branches refusées : {self.t.ligne} feat/a")
        self.contient(r, "  - feat/b : outillage de fin touché (1 fichier(s)) : train d'une seule branche", "      .claude/reglage.json")

    def test_un_claude_md_reste_refuse_a_plusieurs(self):
        self.t.branche("feat/a", {"sous/CLAUDE.md": "c\n"})
        self.t.branche("feat/b")
        r = self.t.lance("--essai", "feat/a", "feat/b")
        self.contient(r, "  - feat/a : outillage de fin touché (1 fichier(s)) : train d'une seule branche")
        self.assertEqual(r.code, 62, r.texte)


if __name__ == "__main__":
    unittest.main()
