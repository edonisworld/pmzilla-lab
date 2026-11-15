"""
finish-single-b3-b6, B6 (design D18, D19, D22) : le train d'une branche. Un fichier `juge`, .claude/ ou un CLAUDE.md est admis quand la liste
n'a qu'une branche (les lignes de l'outillage touché sont écrites avant la question) ; à deux branches ou plus, .claude/ et un CLAUDE.md restent refusés,
un fichier `juge` est admis (R-20261102-43 : jusqu'à 3 branches juges, fichiers juges distincts ; remplace « une branche juge passe seule », retrait
permanent tant que le train porte des branches juges, tests/finish_train/test_plusieurs_juges.py) ; le contrôle 6 d'une
branche n'est plus un refus à l'admission : l'arbre du train en décide (enregistrement par empreinte des fichiers évalués : passe ; aucun : code 83,
rien n'est fusionné, bannière « contrôle 6 »).

Faux déclarés (aide_train.py) : la passe Mac, ci_local et la garde du matin du dépôt jetable ; risque non couvert : le vrai runner complet et le vrai
conteneur, que le train de répétition de la tâche 5.13 éprouve. Le module de contrôles, l'empreinte des fichiers évalués et Git sont les vrais.
"""
import json
import sys
import unittest
from pathlib import Path

from aide_train import AvecTrain, OUTILS, LISTE_JEU

LISTE_CLASSEE = ("# liste fictive classée\ntools/hooks/  #[juge]\ntools/finish_branch.sh  #[juge]\ntools/finish_train.sh  #[juge]\n"
                 "tools/finish_protected.txt  #[juge]\ntests/run_all.sh  #[juge]\n")
PHRASE_UNE_BRANCHE = "outillage de fin dans ce train d'une branche : 1 fichier(s)"
# R-20261102-43 : ne vaut plus que pour .claude/ et CLAUDE.md à plusieurs branches (un fichier `juge` y est admis, jusqu'à 3 branches juges)
PHRASE_REFUS_PLUSIEURS = "outillage de fin touché (1 fichier(s)) : train d'une seule branche"
PHRASE_PLUSIEURS_JUGES = "outillage de fin dans ce train de plusieurs branches"
PHRASE_83 = "jeu d'essai validant absent pour l'arbre du train ; rien n'est fusionné"
BANDEAU_83 = "===== arrêt à contrôle 6 : rien n'est fusionné ====="


def empreinte_de(contenu: Path, arbre: str) -> str:
    sys.path.insert(0, str(OUTILS))
    try:
        import posture_eval_fingerprint
        return posture_eval_fingerprint.fingerprint(contenu, arbre, posture_eval_fingerprint.read_list(LISTE_JEU))
    finally:
        sys.path.remove(str(OUTILS))


class AvecListeClassee(AvecTrain):
    def setUp(self):
        super().setUp()
        self.t.commit_main({"tools/finish_protected.txt": LISTE_CLASSEE}, "liste protégée classée", pousser=True)
        self.t.mettre_a_jour_run()

    def enregistrer_essai(self, empreinte=None, base=None, date="2026-10-30"):
        dossier = self.t.data / "essais" / date
        dossier.mkdir(parents=True, exist_ok=True)
        donnees = {"date": date, "base": base or self.t.main(), "cas": [], "complet": True, "validant": True}
        if empreinte:
            donnees["evaluated_fingerprint"] = empreinte
        (dossier / "resultats.json").write_text(json.dumps(donnees), encoding="utf-8")


class OutillageAUneBranche(AvecListeClassee):
    def test_un_train_d_une_branche_avec_un_fichier_juge_arrive_a_la_question_et_fusionne(self):
        self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n", "tools/outil.sh": "y\n"})
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, f"finish_train : {PHRASE_UNE_BRANCHE}", "      tools/finish_branch.sh")
        self.assertLess(r.texte.index(PHRASE_UNE_BRANCHE), r.texte.index("Terminer le train"))
        self.code(r, 0, "main avancé sur le train")
        self.assertEqual(self.t.main(), self.t.origin_main())
        self.assertEqual(self.t.git("show", "main:tools/finish_branch.sh"), "x")

    # R-20261102-43 : remplace test_la_meme_branche_dans_une_liste_de_deux_est_refusee_avec_la_nouvelle_phrase (« une branche juge passe seule ») ; retrait
    # permanent tant que le train porte des branches juges ; la même branche, dans une liste de deux, est admise avec la ligne de la branche juge de rang 1
    def test_la_meme_branche_dans_une_liste_de_deux_est_admise(self):
        self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n"})
        self.t.branche("feat/y")
        r = self.t.lance("feat/x", "feat/y", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, f"finish_train : {PHRASE_PLUSIEURS_JUGES} (branche juge de rang 1 : feat/x) : 1 fichier(s)", "      tools/finish_branch.sh")
        self.absent(r, PHRASE_REFUS_PLUSIEURS, "fin unitaire", PHRASE_UNE_BRANCHE)
        self.assertEqual(self.t.main(), self.t.origin_main())

    def test_un_train_de_deux_branches_juges_arrive_a_la_question_et_fusionne_les_deux_fichiers(self):
        # R-20261102-43 : vrai lancement (réponse « o »), les lignes des deux branches juges précèdent la question, main porte les deux fichiers
        self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n"})
        self.t.branche("feat/y", {"tools/hooks/y.sh": "y\n"})
        r = self.t.lance("feat/x", "feat/y", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        question = r.texte.index("Terminer le train")
        for rang, nom in ((1, "feat/x"), (2, "feat/y")):
            ligne = f"{PHRASE_PLUSIEURS_JUGES} (branche juge de rang {rang} : {nom}) : 1 fichier(s)"
            self.assertIn(ligne, r.texte)
            self.assertLess(r.texte.index(ligne), question)
        self.code(r, 0, "main avancé sur le train")
        self.assertEqual(self.t.main(), self.t.origin_main())
        self.assertEqual(self.t.git("show", "main:tools/finish_branch.sh"), "x")
        self.assertEqual(self.t.git("show", "main:tools/hooks/y.sh"), "y")

    def test_claude_est_admis_a_une_branche(self):
        self.t.branche("feat/x", {".claude/reglage.json": "{}\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, f"finish_train : {PHRASE_UNE_BRANCHE}", "      .claude/reglage.json")

    def test_un_claude_md_est_admis_a_une_branche(self):
        self.t.branche("feat/x", {"sous/dossier/CLAUDE.md": "c\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, f"finish_train : {PHRASE_UNE_BRANCHE}", "      sous/dossier/CLAUDE.md")

    def test_claude_et_claude_md_sont_refuses_a_deux_branches(self):
        self.t.branche("feat/x", {".claude/reglage.json": "{}\n"})
        self.t.branche("feat/y", {"sous/dossier/CLAUDE.md": "c\n"})
        r = self.t.lance("--essai", "feat/x", "feat/y")
        self.assertEqual(r.code, 62, r.texte)
        self.contient(r, f"  - feat/x : {PHRASE_REFUS_PLUSIEURS}", f"  - feat/y : {PHRASE_REFUS_PLUSIEURS}")

    def test_un_fichier_sensible_garde_sa_regle_de_revue_meme_a_une_branche_avec_un_fichier_juge(self):
        # D18 ne dit rien du fichier `sensible` d'une branche qui touche aussi un fichier `juge` : la règle de revue de D11 continue de s'appliquer (plus strict)
        liste = LISTE_CLASSEE + "tools/mapping_lab.py  #[sensible] vues de la base\n"
        self.t.commit_main({"tools/finish_protected.txt": liste}, "liste avec sensible", pousser=True)
        self.t.mettre_a_jour_run()
        sommet = self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n", "tools/mapping_lab.py": "v\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 62, r.texte)
        self.contient(r, f"feat/x : outil sensible touché (1 fichier(s)) sans revue Opus enregistrée pour le sommet {sommet[:12]} : revue ou fin unitaire")


class Controle6SurLArbre(AvecListeClassee):
    def test_le_controle_6_d_une_branche_n_est_plus_un_refus_a_l_admission(self):
        self.t.branche("feat/x", {"CLAUDE.md": "changé\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertNotEqual(r.code, 62, r.texte)
        self.absent(r, "contrôle 6 refusé", "un jeu d'essai validant vaut pour le sommet de la branche")
        self.contient(r, f"finish_train : {PHRASE_UNE_BRANCHE}")

    def test_un_enregistrement_par_empreinte_de_l_arbre_du_train_passe(self):
        self.t.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.enregistrer_essai(empreinte=empreinte_de(self.t.contenu, self.t.arbre("feat/x")))
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "finish_train : jeu d'essai validant trouvé pour l'arbre du train : 2026-10-30 (0/0) (empreinte des fichiers évalués)")
        self.assertEqual(self.t.main(), self.t.origin_main())

    def test_le_controle_6_est_lu_apres_le_controle_14_et_avant_les_paquets_et_les_passes(self):
        # réécrit (R-114, revue Opus point 6) : le contrôle 14 tourne toujours (sa ligne est « passage du conteneur requis (phase base) », R-20261101-116) et
        # précède le contrôle 6 ; le contrôle 6 reste lu avant le passage du conteneur (repéré à sa première ligne de phase, imprimée par le faux ci) et
        # avant la passe Mac
        self.t.branche("feat/x", {"CLAUDE.md": "changé\n", "db/001.sql": "SELECT 2;\n"})
        self.enregistrer_essai(empreinte=empreinte_de(self.t.contenu, self.t.arbre("feat/x")))
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        a14 = r.texte.index("passage du conteneur requis (phase base)")
        a6 = r.texte.index("jeu d'essai validant trouvé pour l'arbre du train")
        self.assertLess(a14, a6)
        self.assertLess(a6, r.texte.index("ci_passage : phase portable"))
        self.assertLess(a6, r.texte.index("lancement du runner complet"))

    def test_sans_enregistrement_code_83_main_inchange_et_bandeau_controle_6(self):
        self.t.branche("feat/x", {"CLAUDE.md": "changé\n"})
        avant = self.t.instantane()
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 83, PHRASE_83)
        self.contient(r, BANDEAU_83, "\n  CLAUDE.md, une posture")   # les lignes de détail du module sont indentées
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])
        self.assertEqual(self.t.ci_appels(), [], "ni passage du conteneur ni dbtest : le faux ci n'est pas appelé")

    def test_un_enregistrement_d_une_autre_empreinte_ne_compte_pas(self):
        self.t.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.enregistrer_essai(empreinte="sha256:" + "0" * 64)
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 83, PHRASE_83)

    def test_un_enregistrement_valable_pour_le_sommet_seul_ne_vaut_pas_pour_un_autre_arbre_de_train(self):
        # revue de B6, C1 : l'intention du test retiré. origin/main change un autre fichier évalué après la création de la branche : l'arbre du train
        # n'est plus l'arbre du sommet ; ni l'empreinte du sommet, ni un enregistrement sans empreinte dont la base est le sommet ne valent pour lui
        import shutil
        sommet = self.t.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.t.commit_main({"tests/postures/vocabulaire.yaml": "v autre\n"}, "autre fichier évalué", pousser=True)
        self.t.mettre_a_jour_run()
        avant = self.t.instantane()
        self.enregistrer_essai(empreinte=empreinte_de(self.t.contenu, self.t.arbre("feat/x")))
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 83, PHRASE_83)
        self.rien_ne_change(avant)
        shutil.rmtree(self.t.data / "essais" / "2026-10-30")
        self.enregistrer_essai(base=sommet, date="2026-10-29")
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 83, PHRASE_83)
        self.rien_ne_change(avant)

    def test_la_reprise_au_push_rejoue_le_controle_6_sur_l_arbre_et_refuse_en_83_etat_e3(self):
        # Q3 (b) de l'auteur (R-20261030-48) : en S1, le contrôle 6 de l'arbre de main est rejoué ; sans enregistrement : 83, main garde le train
        import shutil
        self.t.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.enregistrer_essai(empreinte=empreinte_de(self.t.contenu, self.t.arbre("feat/x")))
        self.t.etat_fusionne_localement("feat/x")
        tip = self.t.main()
        shutil.rmtree(self.t.data / "essais" / "2026-10-30")
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 83, PHRASE_83)
        self.contient(r, "reprise : main porte déjà le train",
                      "===== arrêt à contrôle 6 : main local porte le train, rien n'est poussé ; relancer la même commande pour reprendre au push =====")
        self.assertEqual(self.t.main(), tip)
        self.assertNotEqual(self.t.distant_main(), tip)

    def test_la_reprise_au_push_avec_l_enregistrement_continue(self):
        self.t.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.enregistrer_essai(empreinte=empreinte_de(self.t.contenu, self.t.arbre("feat/x")))
        self.t.etat_fusionne_localement("feat/x")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "jeu d'essai validant trouvé pour l'arbre du train")

    def test_un_train_de_deux_branches_sans_fichier_protege_passe_par_le_controle_6_de_l_arbre(self):
        self.t.branche("feat/x", {"tests/postures/vocabulaire.yaml": "v modifié\n"})
        self.t.branche("feat/y")
        r = self.t.lance("feat/x", "feat/y", entree="o\n")
        self.code(r, 83, PHRASE_83)
        self.contient(r, BANDEAU_83)

    def test_un_fichier_evalue_inchange_donne_un_controle_6_sans_objet(self):
        self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n"})
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "jeu d'essai validant trouvé", PHRASE_83)


if __name__ == "__main__":
    unittest.main()
