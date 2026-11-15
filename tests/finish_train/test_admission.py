"""
Tâche 2.5 (change finish-train-v1) : l'admission, branche par branche (conception D6 et D18, code 62). Toutes les branches passent tous les
contrôles ; tous les refus sont rapportés d'un coup, suivis de la ligne de relance sans les branches refusées.
"""
import re
import subprocess
import unittest

from aide_train import AvecTrain, CHEMIN_INTERFACE, OUTILS


class Admission(AvecTrain):
    def refuse(self, r, branche, motif):
        self.assertEqual(r.code, 62, r.texte)
        self.assertIn(f"{branche} : {motif}", r.texte)

    def un_refus(self, branche="feat/x", **args):
        return self.t.lance(branche, **args)

    # --- les motifs de D6 et D18, un test chacun
    def test_branche_introuvable(self):
        avant = self.t.instantane()
        r = self.un_refus("feat/fantome")
        self.refuse(r, "feat/fantome", "introuvable en local")
        self.code(r, 62, "branche(s) refusée(s) au train : 1 sur 1 ; rien n'est fusionné", "aucune branche admise")
        self.rien_ne_change(avant)

    def test_branche_deja_dans_origin_main(self):
        self.t.git("branch", "feat/deja", "main")
        r = self.un_refus("feat/deja")
        self.refuse(r, "feat/deja", "déjà contenue dans origin/main")

    def test_worktree_pas_propre(self):
        self.t.branche("feat/x")
        (self.t.dossier_worktree("feat/x") / "sale.txt").write_text("x\n", encoding="utf-8")
        self.refuse(self.un_refus(), "feat/x", "worktree pas propre")

    def test_fichiers_ignores_comptes_sans_jamais_nommer_le_fichier(self):
        self.t.branche("feat/x")
        wt = self.t.dossier_worktree("feat/x")
        (wt / "dossier-x").mkdir()
        (wt / "dossier-x" / "nom-sentinelle-12345.sentinelle").write_text("x\n", encoding="utf-8")
        r = self.un_refus()
        self.refuse(r, "feat/x", "1 fichier(s) ignoré(s) seraient perdus (dossiers : dossier-x)")
        self.absent(r, "nom-sentinelle-12345")
        self.assertNotIn("nom-sentinelle-12345", self.t.log())

    def test_les_exceptions_d_ignores_ne_comptent_pas(self):
        self.t.branche("feat/x")
        wt = self.t.dossier_worktree("feat/x")
        (wt / "__pycache__").mkdir()
        (wt / "__pycache__" / "m.pyc").write_bytes(b"x")
        (wt / ".DS_Store").write_bytes(b"x")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)

    def test_processus_dans_le_worktree(self):
        self.t.branche("feat/x")
        wt = self.t.dossier_worktree("feat/x")
        proc = subprocess.Popen(["sleep", "600"], cwd=wt)   # témoin sans durée fixe : le test l'arrête (addCleanup, y compris en cas d'échec)
        self.addCleanup(proc.kill)
        r = self.un_refus()
        self.assertEqual(r.code, 62, r.texte)
        m = re.search(r"feat/x : un processus a son dossier courant dans son worktree \((\d+) sleep\)", r.texte)
        self.assertIsNotNone(m, r.texte)
        self.assertEqual(int(m.group(1)), proc.pid)

    def test_verification_des_processus_impossible_refuse_la_branche(self):
        self.t.branche("feat/x")
        r = self.un_refus(extra={"FAKE_LSOF_MODE": "casse"})
        self.refuse(r, "feat/x", "vérification des processus impossible")

    def test_controle_19_refuse(self):
        self.t.branche("feat/x", {"tools/outil.sh": "un\n", "openspec/changes/autre/p.md": "modifié\n"})
        r = self.un_refus()
        self.refuse(r, "feat/x", "contrôle 19 refusé : ")
        self.contient(r, "autre")

    def test_controle_5_refuse(self):
        self.t.branche("feat/nouveau", {"tools/outil.sh": "un\n", "openspec/changes/nouveau/p.md": "n\n"})
        r = self.un_refus("feat/nouveau")
        self.refuse(r, "feat/nouveau", "contrôle 5 refusé : ")

    # Remplacé (R-20261030-41, design D19) : test_controle_6_applicable_refuse_la_branche (CLAUDE.md changé, une branche, 62 « contrôle 6 refusé ») par
    # tests/finish_train/test_une_branche.py : le même cas n'est plus un refus à l'admission (test_le_controle_6_d_une_branche_n_est_plus_un_refus_a_l_admission)
    # et l'arbre du train en décide (test_sans_enregistrement_code_83_main_inchange_et_bandeau_controle_6 ; avec enregistrement : test_un_enregistrement_par_empreinte_de_l_arbre_du_train_passe).

    # Retiré (finish-single-b3-b6, B6, tâche 1.1 et R-20261029-39 Q11, design D19) : test_controle_6_qui_passe_grace_a_un_enregistrement_refuse_aussi_la_branche
    # attendait le refus d'une branche dont le contrôle 6 passe ; ce mécanisme est retiré, l'arbre du train décide (tests/finish_train/test_une_branche.py).

    def test_finish_checks_qui_sort_en_2_refuse_la_branche(self):
        self.t.branche("feat/x")
        self.t.remplacer_finish_checks(2)
        r = self.un_refus()
        self.refuse(r, "feat/x", "contrôles impossibles : sortie inattendue de finish_checks (code 2)")

    def test_finish_checks_absent_refuse_la_branche(self):
        self.t.branche("feat/x")
        self.t.commit_main({"tools/finish_checks.py": None}, "sans finish_checks", pousser=True)
        self.t.mettre_a_jour_run()
        r = self.un_refus()
        self.refuse(r, "feat/x", "contrôles impossibles : sortie inattendue de finish_checks (code 2)")

    def test_un_fichier_protege_touche_est_liste_une_seule_fois(self):
        # « protected_judges » est pris dans le JSON de finish_checks ; la liste de sécurité du script (.claude/, CLAUDE.md) ne double rien
        # B6 (tâche 1.1) : à une branche, l'outillage protégé est admis ; la ligne le dit une fois
        self.t.branche("feat/x", {"tools/finish_branch.sh": "x\n", "tools/outil.sh": "y\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train d'une branche : 1 fichier(s)")
        self.assertEqual(r.texte.count("      tools/finish_branch.sh"), 1)

    def test_une_branche_qui_ne_change_que_le_verrou_npm_est_admise_avec_la_vraie_liste_protegee(self):
        # décision de l'auteur du 2026-10-27 : la vraie liste tools/finish_protected.txt (lue, pas celle de la fixture) ne protège pas le verrou npm de
        # Mothra ; sans cela, le conseil « npm ci dans le worktree de la branche qui change le verrou » (décision B) ne serait jamais atteignable
        vraie = (OUTILS / "finish_protected.txt").read_text(encoding="utf-8")
        self.assertNotIn("mothra/package-lock.json", vraie.splitlines())
        self.t.commit_main({"tools/finish_protected.txt": vraie}, "vraie liste protégée", pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x", {"mothra/package-lock.json": "{}\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.assertNotIn("outillage de fin touché", r.texte)

    def pose_la_vraie_liste_protegee(self):
        vraie = (OUTILS / "finish_protected.txt").read_text(encoding="utf-8")
        self.t.commit_main({"tools/finish_protected.txt": vraie}, "vraie liste protégée", pousser=True)
        self.t.mettre_a_jour_run()

    def test_package_json_racine_de_mothra_et_verrou_refuses_en_62_avec_la_vraie_liste(self):
        # décision (ii) de l'auteur du 2026-10-27 : mothra/package.json (espace npm, engines, scripts racine) reste protégé ; une branche qui le touche,
        # verrou compris, passe par une fin unitaire ; B6 (tâche 1.1) : seule, elle est admise dans un train d'une branche ; R-20261102-43 (remplace « une
        # branche juge passe seule », retrait permanent tant que le train porte des branches juges) : avec une branche sans fichier juge, elle est aussi
        # admise, et la ligne la désigne comme branche juge de rang 1
        self.pose_la_vraie_liste_protegee()
        self.t.branche("feat/x", {"mothra/package.json": "{}\n", "mothra/package-lock.json": "{}\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train d'une branche : 1 fichier(s)", "      mothra/package.json")
        self.t.branche("feat/y")
        r = self.t.lance("--essai", "feat/x", "feat/y")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train de plusieurs branches (branche juge de rang 1 : feat/x) : 1 fichier(s)", "      mothra/package.json")
        self.absent(r, "train d'une seule branche")

    def test_node_version_de_mothra_est_admis_a_une_branche_avec_la_vraie_liste(self):
        self.pose_la_vraie_liste_protegee()
        self.t.branche("feat/x", {"mothra/.node-version": "22\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train d'une branche : 1 fichier(s)")

    def test_package_json_d_un_sous_dossier_de_mothra_et_verrou_admis_avec_la_vraie_liste(self):
        self.pose_la_vraie_liste_protegee()
        self.t.branche("feat/x", {"mothra/front/package.json": "{}\n", "mothra/package-lock.json": "{}\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.assertNotIn("outillage de fin touché", r.texte)

    # --- fichiers ignorés : l'exemption de node_modules sous mothra/ (R-148 u16, règle de l'ancienne fin unitaire)
    def test_node_modules_sous_mothra_est_exempte(self):
        self.t.branche("feat/x")
        dossier = self.t.dossier_worktree("feat/x") / "mothra" / "serveur" / "node_modules" / "paquet"
        dossier.mkdir(parents=True)
        (dossier / "index.js").write_text("x\n", encoding="utf-8")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)

    def test_node_modules_hors_de_mothra_est_compte(self):
        self.t.branche("feat/x")
        dossier = self.t.dossier_worktree("feat/x") / "outils" / "node_modules" / "paquet"
        dossier.mkdir(parents=True)
        (dossier / "index.js").write_text("x\n", encoding="utf-8")
        r = self.un_refus()
        self.refuse(r, "feat/x", "1 fichier(s) ignoré(s) seraient perdus (dossiers : outils)")

    def test_un_autre_fichier_ignore_sous_mothra_est_compte_meme_a_cote_de_node_modules(self):
        self.t.branche("feat/x")
        racine = self.t.dossier_worktree("feat/x") / "mothra" / "serveur"
        (racine / "node_modules" / "paquet").mkdir(parents=True)
        (racine / "node_modules" / "paquet" / "index.js").write_text("x\n", encoding="utf-8")
        (racine / "reste.sentinelle").write_text("x\n", encoding="utf-8")
        r = self.un_refus()
        self.refuse(r, "feat/x", "1 fichier(s) ignoré(s) seraient perdus (dossiers : mothra)")

    # --- R-148 u18 : mothra/front/dist, même règle (vrai dossier ignoré)
    def test_dist_de_mothra_front_est_exempte(self):
        self.t.branche("feat/x")
        dossier = self.t.dossier_worktree("feat/x") / "mothra" / "front" / "dist" / "assets"
        dossier.mkdir(parents=True)
        (dossier / "app.js").write_text("x\n", encoding="utf-8")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)

    def test_dist_ailleurs_est_compte(self):
        self.t.branche("feat/x")
        dossier = self.t.dossier_worktree("feat/x") / "autre" / "dist"
        dossier.mkdir(parents=True)
        (dossier / "app.js").write_text("x\n", encoding="utf-8")
        r = self.un_refus()
        self.refuse(r, "feat/x", "1 fichier(s) ignoré(s) seraient perdus (dossiers : autre)")

    # --- lien symbolique et dossier suivi en partie : comptés, pour node_modules comme pour dist
    def exclure(self, motif):
        with open(self.t.contenu / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:
            f.write(motif + "\n")

    def lien_vers_dossier(self, wt, chemin):
        cible = self.t.dossier / "cible-lien"
        cible.mkdir(exist_ok=True)
        (cible / "f.txt").write_text("x\n", encoding="utf-8")
        lien = wt / chemin
        lien.parent.mkdir(parents=True, exist_ok=True)
        lien.symlink_to(cible)

    def suivi_en_partie(self, wt, dossier):
        (wt / dossier).mkdir(parents=True, exist_ok=True)
        (wt / dossier / "t.js").write_text("t\n", encoding="utf-8")
        self.t.git("add", "-f", f"{dossier}/t.js", cwd=wt)
        self.t.git("commit", "-q", "-m", "suivi en partie", cwd=wt)
        (wt / dossier / "sortie").mkdir()
        (wt / dossier / "sortie" / "x").write_text("x\n", encoding="utf-8")

    def test_dist_lien_symbolique_est_compte(self):
        self.t.branche("feat/x")
        self.exclure("mothra/front/dist")
        self.lien_vers_dossier(self.t.dossier_worktree("feat/x"), "mothra/front/dist")
        r = self.un_refus()
        self.refuse(r, "feat/x", "1 fichier(s) ignoré(s) seraient perdus (dossiers : mothra)")

    def test_dist_suivi_en_partie_est_compte(self):
        self.t.branche("feat/x")
        self.suivi_en_partie(self.t.dossier_worktree("feat/x"), "mothra/front/dist")
        r = self.un_refus()
        self.refuse(r, "feat/x", "1 fichier(s) ignoré(s) seraient perdus (dossiers : mothra)")

    def test_node_modules_lien_symbolique_est_compte(self):
        self.t.branche("feat/x")
        self.exclure("mothra/serveur/node_modules")
        self.lien_vers_dossier(self.t.dossier_worktree("feat/x"), "mothra/serveur/node_modules")
        r = self.un_refus()
        self.refuse(r, "feat/x", "1 fichier(s) ignoré(s) seraient perdus (dossiers : mothra)")

    def test_node_modules_suivi_en_partie_est_compte(self):
        self.t.branche("feat/x")
        self.suivi_en_partie(self.t.dossier_worktree("feat/x"), "mothra/serveur/node_modules")
        r = self.un_refus()
        self.refuse(r, "feat/x", "1 fichier(s) ignoré(s) seraient perdus (dossiers : mothra)")

    def test_finish_checks_sortie_3(self):
        self.t.branche("spike/x")
        r = self.un_refus("spike/x")
        self.refuse(r, "spike/x", "non contrôlable : ")
        self.contient(r, "branche spike/*")

    def test_finish_checks_sortie_4(self):
        self.t.branche_orpheline("feat/orpheline")
        r = self.un_refus("feat/orpheline")
        self.refuse(r, "feat/orpheline", "contrôles impossibles : ")
        self.contient(r, "base commune introuvable")

    # B6 (tâche 1.1, design D18) : les trois cas ci-dessous étaient refusés en 62 « fin unitaire » ; à une branche ils sont admis. R-20261102-43 : à deux
    # branches ou plus, un fichier juge est admis (jusqu'à 3 branches juges, fichiers juges distincts) ; .claude/ et un CLAUDE.md restent refusés avec
    # « train d'une seule branche » (remplace « une branche juge passe seule » ; retrait permanent tant que le train porte des branches juges)
    def test_fichier_protege(self):
        self.t.branche("feat/x", {"tools/finish_branch.sh": "#!/bin/bash\nexit 0\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train d'une branche : 1 fichier(s)", "      tools/finish_branch.sh")

    def test_chemin_sous_claude(self):
        self.t.branche("feat/x", {".claude/reglage.json": "{}\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train d'une branche : 1 fichier(s)", "      .claude/reglage.json")

    def test_claude_md_dans_un_sous_dossier(self):
        self.t.branche("feat/x", {"sous/dossier/CLAUDE.md": "c\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "outillage de fin dans ce train d'une branche : 1 fichier(s)", "      sous/dossier/CLAUDE.md")

    def test_changement_de_la_base_admis_au_niveau_de_la_branche(self):
        # le contrôle 14 ne refuse pas par branche : il est jugé sur l'arbre du train (D6, D9)
        self.t.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        # la phrase neuve du contrôle 14 (Q225 a, R-20261101-116), aussi stricte qu'avant : « passage du conteneur requis (phase base) »
        self.contient(r, "passage du conteneur requis (phase base)")

    # --- plusieurs refus, une seule passe
    def test_deux_branches_refusees_rapportees_ensemble_avec_la_ligne_de_relance(self):
        self.t.branche("feat/ok")
        self.t.branche("feat/sale")
        # R-20261102-43 : un fichier juge n'est plus un refus à plusieurs ; la branche refusée touche .claude/, toujours refusé à plusieurs
        self.t.branche("feat/protegee", {".claude/reglage.json": "{}\n"})
        (self.t.dossier_worktree("feat/sale") / "sale.txt").write_text("x\n", encoding="utf-8")
        avant = self.t.instantane()
        r = self.t.lance("feat/sale", "feat/ok", "feat/protegee")
        self.code(r, 62, "branche(s) refusée(s) au train : 2 sur 3 ; rien n'est fusionné",
                  f"ligne sans les branches refusées : {self.t.ligne} feat/ok")
        self.contient(r, "  - feat/sale : worktree pas propre", "  - feat/protegee : outillage de fin touché (1 fichier(s)) : train d'une seule branche")
        self.rien_ne_change(avant)

    def test_la_ligne_de_relance_garde_l_ordre_des_branches_admises(self):
        self.t.branche("feat/a1")
        self.t.branche("feat/b1")
        self.t.branche("feat/c1")
        (self.t.dossier_worktree("feat/b1") / "sale.txt").write_text("x\n", encoding="utf-8")
        r = self.t.lance("feat/c1", "feat/b1", "feat/a1")
        self.code(r, 62, f"ligne sans les branches refusées : {self.t.ligne} feat/c1 feat/a1")

    def test_la_ligne_de_relance_du_62_protege_les_noms_par_printf_q(self):
        self.t.branche("feat/a&b")
        self.t.branche("feat/sale")
        (self.t.dossier_worktree("feat/sale") / "sale.txt").write_text("x\n", encoding="utf-8")
        r = self.t.lance("feat/a&b", "feat/sale")
        self.code(r, 62, f"ligne sans les branches refusées : {self.t.ligne} feat/a\\&b")


class FrontAdmis(AvecTrain):
    """finish-e2e-proof-shared, D6 : l'exclusion du front de Mothra est retirée (les tests de l'exclusion, décision R-20261029-29, Q2 de B2, sont
    retirés avec elle). Une branche qui change un chemin d'interface est admise ; l'arbre du train décide, à l'étape de la passe de bout en bout."""

    def test_une_branche_qui_change_un_chemin_d_interface_est_admise_sans_motif_d_exclusion(self):
        self.t.branche("feat/front", {CHEMIN_INTERFACE: "x\n"})
        self.t.branche("feat/ok")
        r = self.t.lance("--essai", "feat/front", "feat/ok")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "change le front de Mothra", "fin unitaire", "liste d'exclusion", "branche(s) refusée(s)")

    def test_le_verrou_npm_de_mothra_n_est_plus_un_motif_de_refus(self):
        self.t.branche("feat/verrou", {"mothra/package-lock.json": "{}\n"})
        r = self.t.lance("--essai", "feat/verrou")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "change le front de Mothra")

    def test_le_controle_16_est_exige_present_dans_la_sortie_du_module_sans_etre_un_motif_de_refus(self):
        # un module de contrôles qui n'a pas de contrôle 16 : la branche est refusée comme pour tout contrôle absent (format contractuel) ;
        # avec le contrôle 16 refusé (aucune ligne e2e), elle reste admise : l'arbre du train décide
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        reel = (OUTILS / "finish_checks.py").read_text(encoding="utf-8")
        sans_16 = reel.replace('_controle("16"', '_controle("99"')   # le contrôle existe encore, sous un autre identifiant : le 16 est absent de la sortie
        self.assertNotEqual(reel, sans_16, "le renommage du contrôle 16 dans la copie du module doit changer le texte")
        self.t.commit_main({"tools/finish_checks.py": sans_16}, "module sans contrôle 16", pousser=True)
        self.t.mettre_a_jour_run()
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 62, r.texte)
        self.contient(r, "  - feat/x : contrôles impossibles : contrôle 16 absent de la sortie de finish_checks")


if __name__ == "__main__":
    unittest.main()
