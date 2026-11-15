"""
Tâche 2.2 (change finish-train-v1) : le lancement de tools/finish_train.sh, codes 60 (usage), 61 (lancement refusé) et 78 (dossiers du lab), avec leurs
phrases (conception D1 et D18). Chaque refus laisse tout en l'état. Aide : tests/finish_train/aide_train.py.

    uv run python -m unittest discover -s tests/finish_train -q -f
"""
import unittest

from aide_train import AvecTrain, E1, E2


class Usage(AvecTrain):
    def test_aucune_branche(self):
        avant = self.t.instantane()
        self.code(self.t.lance(), 60, self.t.usage)
        self.rien_ne_change(avant)

    def test_essai_sans_branche(self):
        self.code(self.t.lance("--essai"), 60, self.t.usage)

    def test_la_ligne_vient_des_dossiers_du_lab(self):
        # le chemin de la ligne est celui du dossier d'exécution des dossiers du lab (jamais un chemin écrit en dur dans le script)
        r = self.t.lance()
        self.assertIn(f"usage : bash {self.t.run}/tools/finish_train.sh ", r.texte)

    def test_nom_en_double(self):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        self.code(self.t.lance("feat/x", "feat/x"), 60, self.t.usage)
        self.rien_ne_change(avant)

    def test_sept_noms(self):
        noms = [f"feat/b{k}" for k in range(7)]
        self.code(self.t.lance(*noms), 60, self.t.usage)

    def test_six_noms_ne_sont_pas_un_refus_d_usage(self):
        noms = [f"feat/b{k}" for k in range(6)]
        r = self.t.lance(*noms)
        self.code(r, 62, "branche(s) refusée(s) au train : 6 sur 6 ; rien n'est fusionné")   # aucune n'existe : refus à l'admission, pas à l'usage

    def test_option_inconnue(self):
        self.t.branche("feat/x")
        self.code(self.t.lance("--foo", "feat/x"), 60, self.t.usage)
        self.code(self.t.lance("feat/x", "--force"), 60, self.t.usage)

    def test_help_est_une_option_inconnue(self):
        # D1 : toute autre option donne 60 ; les codes sont déclarés dans l'en-tête du script seulement
        self.code(self.t.lance("--help"), 60, self.t.usage)
        self.code(self.t.lance("-h", "feat/x"), 60, self.t.usage)


class LancementRefuse(AvecTrain):
    def test_hors_du_dossier_d_execution(self):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", script=self.t.contenu / "tools" / "finish_train.sh", cwd=self.t.contenu)
        self.code(r, 61, "lancement refusé : à lancer depuis le dossier d'exécution")
        self.rien_ne_change(avant)

    PHRASE_PAS_DETACHE = "lancement refusé : dossier d'exécution modifié ou pas détaché"

    def test_dossier_d_execution_modifie(self):
        self.t.branche("feat/x")
        (self.t.run / "README.md").write_text("modifié\n", encoding="utf-8")
        r = self.t.lance("feat/x")
        self.code(r, 61, self.PHRASE_PAS_DETACHE)
        self.assertIn(f"===== arrêt à lancement : {E1} =====", r.texte)

    def test_dossier_d_execution_sur_une_branche(self):
        self.t.branche("feat/x")
        self.t.git("checkout", "-q", "-b", "run-sur-branche", cwd=self.t.run)
        avant = self.t.instantane()
        r = self.t.lance("feat/x")
        self.code(r, 61, self.PHRASE_PAS_DETACHE)
        self.assertIn(f"===== arrêt à lancement : {E1} =====", r.texte)
        self.rien_ne_change(avant)

    def test_dossier_d_execution_detache_sur_main_local_est_accepte(self):
        self.t.branche("feat/x")
        self.assertEqual(self.t.git("rev-parse", "HEAD", cwd=self.t.run), self.t.main())
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)

    def test_dossier_d_execution_detache_ailleurs_est_refuse_a_la_detection_de_l_etat(self):
        # décision du 2026-10-27 (D1, D5) : la position est revérifiée après le fetch, avec l'état réel de la bannière (E2 en S0)
        self.t.branche("feat/x")
        autre = self.t.commit_sans_lien()
        self.t.detacher_le_dossier_d_execution(autre)
        avant = self.t.instantane()
        r = self.t.lance("feat/x")
        self.code(r, 61, f"lancement refusé : dossier d'exécution détaché sur {autre[:12]}, ni main local, ni origin/main, ni la base du train déjà poussé")
        self.assertIn(f"===== arrêt à état des références : {E2} =====", r.texte)
        self.rien_ne_change(avant)

    def test_dossier_d_execution_en_retard_sur_main_est_refuse_a_la_detection_de_l_etat(self):
        self.t.branche("feat/x")
        ancien = self.t.main()
        self.t.commit_main({"tools/autre.sh": "a\n"}, "main avance", pousser=True)
        self.t.detacher_le_dossier_d_execution(ancien)
        avant = self.t.instantane()
        r = self.t.lance("feat/x")
        self.code(r, 61, f"lancement refusé : dossier d'exécution détaché sur {ancien[:12]}, ni main local, ni origin/main, ni la base du train déjà poussé")
        self.assertIn(f"===== arrêt à état des références : {E2} =====", r.texte)
        self.rien_ne_change(avant)

    def test_session_claude_code_refusee_avant_le_verrou(self):
        self.t.branche("feat/x")
        verrou = self.t.verrou_etranger()
        r = self.t.lance("feat/x", extra={"CLAUDECODE": "1"})
        # 61 et non 67 : le refus précède la prise du verrou ; le verrou d'un autre reste tel quel
        self.code(r, 61, "lancement refusé : session Claude Code ; le train se termine dans le Terminal de l'auteur")
        self.assertEqual((verrou / "jeton").read_text(encoding="utf-8"), "jeton-d-un-autre\n")

    def test_espace_de_travail_pas_sur_main(self):
        self.t.branche("feat/x")
        self.t.git("checkout", "-q", "-b", "ailleurs")
        avant = self.t.instantane()
        self.code(self.t.lance("feat/x"), 61, "lancement refusé : l'espace de travail n'est pas sur main")
        self.rien_ne_change(avant)

    def test_espace_de_travail_pas_propre(self):
        self.t.branche("feat/x")
        (self.t.contenu / "sale.txt").write_text("x\n", encoding="utf-8")
        avant = self.t.instantane()
        self.code(self.t.lance("feat/x"), 61, "lancement refusé : l'espace de travail n'est pas propre")
        self.rien_ne_change(avant)

    def test_un_fichier_non_suivi_sous_bmad_output_ne_refuse_pas_au_depart(self):
        # R-20261102-6 : un livrable de posture non suivi sous _bmad-output/ n'est pas un motif de refus 61
        self.t.branche("feat/x")
        (self.t.contenu / "_bmad-output" / "pmzilla").mkdir(parents=True)
        (self.t.contenu / "_bmad-output" / "pmzilla" / "2026-11-02-livrable.md").write_text("x\n", encoding="utf-8")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)

    def test_des_noms_avec_espace_et_guillemet_sous_bmad_output_ne_refusent_pas_au_depart(self):
        self.t.branche("feat/x")
        dossier = self.t.contenu / "_bmad-output" / "pmzilla"
        dossier.mkdir(parents=True)
        (dossier / "livrable avec espace.md").write_text("x\n", encoding="utf-8")
        (dossier / 'livrable "cité".md').write_text("x\n", encoding="utf-8")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)

    def test_un_fichier_indexe_sous_bmad_output_refuse(self):
        # un fichier ajouté à l'index (« A  ») n'est plus « non suivi » : refus 61
        self.t.branche("feat/x")
        dossier = self.t.contenu / "_bmad-output" / "pmzilla"
        dossier.mkdir(parents=True)
        (dossier / "indexe.md").write_text("x\n", encoding="utf-8")
        self.t.git("add", "_bmad-output/pmzilla/indexe.md")
        avant = self.t.instantane()
        self.code(self.t.lance("feat/x"), 61, "lancement refusé : l'espace de travail n'est pas propre")
        self.rien_ne_change(avant)

    def test_un_fichier_non_suivi_hors_bmad_output_refuse_toujours(self):
        # R-20261102-6 : seul le préfixe _bmad-output/ est excepté ; un nom voisin ne l'est pas
        self.t.branche("feat/x")
        (self.t.contenu / "_bmad-output-autre").mkdir()
        (self.t.contenu / "_bmad-output-autre" / "sale.md").write_text("x\n", encoding="utf-8")
        avant = self.t.instantane()
        self.code(self.t.lance("feat/x"), 61, "lancement refusé : l'espace de travail n'est pas propre")
        self.rien_ne_change(avant)

    def test_un_fichier_suivi_modifie_sous_bmad_output_refuse(self):
        # R-20261102-6 : l'exception ne vaut que pour les fichiers non suivis
        self.t.commit_main({"_bmad-output/pmzilla/suivi.md": "a\n"}, "livrable suivi", pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x")
        (self.t.contenu / "_bmad-output" / "pmzilla" / "suivi.md").write_text("b\n", encoding="utf-8")
        avant = self.t.instantane()
        self.code(self.t.lance("feat/x"), 61, "lancement refusé : l'espace de travail n'est pas propre")
        self.rien_ne_change(avant)

    def test_un_fichier_ignore_de_l_espace_de_travail_ne_refuse_pas(self):
        self.t.branche("feat/x")
        (self.t.contenu / "garde.sentinelle").write_text("x\n", encoding="utf-8")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)

    def test_dossier_courant_dans_le_worktree_d_une_branche_listee(self):
        self.t.branche("feat/x")
        wt = self.t.dossier_worktree("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", cwd=wt)
        self.code(r, 61, "lancement refusé : le dossier courant est dans le worktree de feat/x")
        self.rien_ne_change(avant)

    def test_identite_git_absente(self):
        self.t.branche("feat/x")
        self.t.sans_identite()
        avant = self.t.instantane()
        self.code(self.t.lance("feat/x"), 61, "lancement refusé : identité Git de l'auteur absente")
        self.rien_ne_change(avant)


class DossiersDuLab(AvecTrain):
    def test_dossiers_du_lab_introuvables(self):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"PMZILLA_LAB_WORKSPACE": str(self.t.dossier / "absent")})
        self.assertEqual(r.code, 78, r.texte)
        self.contient(r, "chemins du lab")
        self.rien_ne_change(avant)


if __name__ == "__main__":
    unittest.main()
