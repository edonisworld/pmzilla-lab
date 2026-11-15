"""
finish-single-b3-b6, B4 (design D11 et D12) : l'admission du train selon la classe de l'outillage protégé, lue dans le JSON du module de contrôles seul.
Un fichier `juge` est admis (B6, puis R-20261102-43 : jusqu'à 3 branches juges, fichiers juges distincts) ; un fichier `sensible` n'est admis qu'avec une ligne de revue Opus enregistrée pour le sommet exact de la
branche (liste des branches prêtes de R-166, lue par tools/train_ready.py, refus par défaut) ; la ligne « outil sensible admis… » précède la question.

Faux déclaré : l'enveloppe de tools/finish_checks.py qui retire les deux champs de classe de la sortie JSON du vrai module (cas « sortie sans les
champs de classe ») ; risque non couvert : un module qui renvoie des champs de classe faux, ce que tests/finish_checks prouve sur le vrai module.
"""
import unittest

from aide_train import AvecTrain, OUTILS

LISTE_CLASSEE = ("# liste fictive classée\ntools/hooks/  #[juge]\ntools/finish_branch.sh  #[juge]\ntools/finish_train.sh  #[juge]\n"
                 "tools/finish_protected.txt  #[juge]\ntests/run_all.sh  #[juge]\ntools/mapping_lab.py  #[sensible] vues de la base\n"
                 "tools/context_lab.py  #[sensible] base\n")
ENVELOPPE_SANS_CLASSES = (
    "import io, json, sys\nfrom contextlib import redirect_stdout\nfrom pathlib import Path\n"
    "sys.path.insert(0, str(Path(__file__).resolve().parent))\nimport finish_checks_reel\n"
    "tampon = io.StringIO()\nwith redirect_stdout(tampon):\n    code = finish_checks_reel.main()\n"
    "donnees = json.loads(tampon.getvalue())\ndonnees.pop('protected_judges', None)\ndonnees.pop('protected_sensitive', None)\n"
    "print(json.dumps(donnees, ensure_ascii=False))\nsys.exit(code)\n")
FORMAT = "# pmzilla-train-pretes format 1"
PHRASE_ABSENTE = "contrôles impossibles : classes de l'outillage protégé absentes de la sortie de finish_checks"


class ClassesAdmission(AvecTrain):
    def setUp(self):
        super().setUp()
        self.t.commit_main({"tools/finish_protected.txt": LISTE_CLASSEE}, "liste protégée classée", pousser=True)
        self.t.mettre_a_jour_run()

    def inscrire(self, branche, sommet, revue="faite", brut=None):
        dossier = self.t.data / "train-auto"
        dossier.mkdir(parents=True, exist_ok=True)
        ligne = "\t".join((branche, sommet, "b" * 40, revue, "2026-10-30T10:00:00Z"))
        (dossier / "pretes.tsv").write_text(brut if brut is not None else f"{FORMAT}\n{ligne}\n", encoding="utf-8")

    def refuse(self, r, branche, motif):
        self.assertEqual(r.code, 62, r.texte)
        if motif.startswith("sans revue"):
            self.assertRegex(r.texte, rf"{branche} : outil sensible touché \(\d+ fichier\(s\)\) {motif}")
        else:
            self.assertIn(f"{branche} : {motif}", r.texte)

    # --- juge
    # B6 (tâche 1.1, design D18) : à une branche un fichier `juge` est admis (ligne « outillage de fin dans ce train d'une branche »). R-20261102-43 : à
    # deux branches juges ou plus (jusqu'à 3) il est admis aussi, tant que les fichiers juges diffèrent (ligne « branche juge de rang … ») ; deux branches
    # juges sur le même fichier juge sont refusées, la revue enregistrée n'y change rien. Remplace : « une branche juge passe seule » (refus « train d'une
    # seule branche » pour un fichier `juge`) ; retrait : permanent tant que le train porte des branches juges. Ce refus ne vaut plus que pour .claude/ et CLAUDE.md
    def test_un_fichier_juge_est_admis_a_une_branche_et_a_deux_quand_les_fichiers_juges_different(self):
        self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n", "tools/outil.sh": "y\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train d'une branche : 1 fichier(s)", "      tools/finish_branch.sh")
        self.t.branche("feat/y", {"tools/hooks/y.sh": "z\n"})
        r = self.t.lance("--essai", "feat/x", "feat/y")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train de plusieurs branches (branche juge de rang 1 : feat/x) : 1 fichier(s)", "      tools/finish_branch.sh",
                      "outillage de fin dans ce train de plusieurs branches (branche juge de rang 2 : feat/y) : 1 fichier(s)", "      tools/hooks/y.sh")
        self.absent(r, "train d'une seule branche")

    def test_deux_branches_juges_sur_le_meme_fichier_juge_sont_refusees_meme_avec_une_revue_enregistree(self):
        sommet = self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n"})
        self.t.branche("feat/y", {"tools/finish_branch.sh": "y\n"})
        self.inscrire("feat/x", sommet)
        r = self.t.lance("--essai", "feat/x", "feat/y")
        self.refuse(r, "feat/y", "fichier juge tools/finish_branch.sh touché aussi par la branche de rang 1 (rang 2 ici) : deux branches juges ne passent pas ensemble")

    def test_un_fichier_juge_et_un_fichier_sensible_a_une_branche_avec_revue_sont_admis_avec_les_deux_lignes(self):
        sommet = self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n", "tools/mapping_lab.py": "v\n"})
        self.inscrire("feat/x", sommet)
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train d'une branche : 1 fichier(s)", f"outil sensible admis après revue Opus du sommet {sommet[:12]} : feat/x")

    # R-20261102-43 (remplace le refus juge « train d'une seule branche » de ce cas ; retrait permanent tant que le train porte des branches juges) : à deux
    # branches, la règle de revue du fichier `sensible` (D11) s'applique comme à une branche, aussi stricte qu'avant
    def test_un_fichier_juge_et_un_fichier_sensible_a_deux_branches_avec_revue_sont_admis_avec_les_deux_lignes(self):
        sommet = self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n", "tools/mapping_lab.py": "v\n"})
        self.t.branche("feat/y")
        self.inscrire("feat/x", sommet)
        r = self.t.lance("--essai", "feat/x", "feat/y")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train de plusieurs branches (branche juge de rang 1 : feat/x) : 1 fichier(s)",
                      f"outil sensible admis après revue Opus du sommet {sommet[:12]} : feat/x")
        self.absent(r, "train d'une seule branche")

    def test_un_fichier_juge_et_un_fichier_sensible_a_deux_branches_sans_revue_donnent_le_refus_sensible(self):
        sommet = self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n", "tools/mapping_lab.py": "v\n"})
        self.t.branche("feat/y")
        r = self.t.lance("--essai", "feat/x", "feat/y")
        self.refuse(r, "feat/x", f"sans revue Opus enregistrée pour le sommet {sommet[:12]} : revue ou fin unitaire")
        self.absent(r, "outil sensible admis", "train d'une seule branche")

    # --- sensible sans revue
    def test_sensible_sans_aucun_enregistrement_est_refuse(self):
        sommet = self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n", "tools/context_lab.py": "d\n"})
        r = self.t.lance("--essai", "feat/x")
        self.refuse(r, "feat/x", f"outil sensible touché (2 fichier(s)) sans revue Opus enregistrée pour le sommet {sommet[:12]} : revue ou fin unitaire")
        self.contient(r, "      tools/context_lab.py", "      tools/mapping_lab.py")
        self.absent(r, "outil sensible admis")

    def test_sensible_avec_un_enregistrement_d_un_autre_sommet_est_refuse(self):
        sommet = self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.inscrire("feat/x", "c" * 40)
        r = self.t.lance("--essai", "feat/x")
        self.refuse(r, "feat/x", f"outil sensible touché (1 fichier(s)) sans revue Opus enregistrée pour le sommet {sommet[:12]} : revue ou fin unitaire")

    def test_sensible_avec_la_ligne_d_une_autre_branche_est_refuse(self):
        sommet = self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.inscrire("feat/y", sommet)
        r = self.t.lance("--essai", "feat/x")
        self.refuse(r, "feat/x", "sans revue Opus enregistrée pour le sommet")

    def test_sensible_avec_une_revue_non_requise_est_refuse(self):
        sommet = self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.inscrire("feat/x", sommet, revue="non-requise")
        r = self.t.lance("--essai", "feat/x")
        self.refuse(r, "feat/x", "sans revue Opus enregistrée pour le sommet")

    def test_sensible_avec_une_liste_illisible_est_refuse(self):
        self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.inscrire("feat/x", "", brut="MOT-SANS-TABULATION\n")
        r = self.t.lance("--essai", "feat/x")
        self.refuse(r, "feat/x", "sans revue Opus enregistrée pour le sommet")

    def test_sensible_apres_un_nouveau_commit_la_revue_du_sommet_precedent_ne_vaut_plus(self):
        premier = self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.inscrire("feat/x", premier)
        self.t.valider(self.t.dossier_worktree("feat/x"), {"tools/context_lab.py": "d\n"}, "suite")
        r = self.t.lance("--essai", "feat/x")
        self.refuse(r, "feat/x", "sans revue Opus enregistrée pour le sommet")
        self.contient(r, self.sha12("feat/x"))

    # --- sensible avec revue
    def test_sensible_avec_la_revue_du_sommet_exact_est_admis_avec_sa_ligne(self):
        sommet = self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.inscrire("feat/x", sommet)
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, f"finish_train : outil sensible admis après revue Opus du sommet {sommet[:12]} : feat/x", "      tools/mapping_lab.py")
        self.absent(r, "sans revue Opus")

    def test_la_ligne_d_admission_precede_la_question(self):
        sommet = self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.inscrire("feat/x", sommet)
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        ligne = f"outil sensible admis après revue Opus du sommet {sommet[:12]} : feat/x"
        self.assertIn(ligne, r.texte)
        self.assertIn("Terminer le train (1 branche(s)) ? (o/n)", r.texte)
        self.assertLess(r.texte.index(ligne), r.texte.index("Terminer le train"))

    def test_le_train_n_ecrit_pas_la_liste_des_branches_pretes(self):
        sommet = self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.inscrire("feat/x", sommet)
        fichier = self.t.data / "train-auto" / "pretes.tsv"
        avant = fichier.read_bytes()
        self.t.lance("feat/x", entree="n\n")
        self.assertEqual(fichier.read_bytes(), avant)
        self.assertEqual(sorted(p.name for p in fichier.parent.iterdir()), ["pretes.tsv"])

    def test_une_branche_sans_fichier_protege_n_a_besoin_d_aucune_revue(self):
        self.t.branche("feat/x", {"tools/outil.sh": "y\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "outil sensible", "outillage de fin touché")

    def test_deux_branches_l_une_revue_l_autre_non_seule_la_seconde_est_refusee(self):
        premier = self.t.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.t.branche("feat/y", {"tools/context_lab.py": "d\n"})
        self.inscrire("feat/x", premier)
        r = self.t.lance("--essai", "feat/x", "feat/y")
        self.refuse(r, "feat/y", "outil sensible touché (1 fichier(s)) sans revue Opus enregistrée pour le sommet")
        self.code(r, 62, f"ligne sans les branches refusées : {self.t.ligne} feat/x")

    # --- sortie du module sans les classes
    def test_une_sortie_du_module_sans_les_champs_de_classe_est_refusee(self):
        reel = (OUTILS / "finish_checks.py").read_text(encoding="utf-8")
        self.t.commit_main({"tools/finish_checks_reel.py": reel, "tools/finish_checks.py": ENVELOPPE_SANS_CLASSES}, "enveloppe sans classes", pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x", {"tools/outil.sh": "y\n"})
        r = self.t.lance("--essai", "feat/x")
        self.refuse(r, "feat/x", PHRASE_ABSENTE)

    # --- statique : les classes ne sont lues que par le module
    def test_le_train_ne_lit_pas_la_liste_protegee_lui_meme(self):
        code = "\n".join(l for l in (OUTILS / "finish_train.sh").read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn("finish_protected", code)
        self.assertIn("protected_judges", code)
        self.assertIn("protected_sensitive", code)


if __name__ == "__main__":
    unittest.main()
