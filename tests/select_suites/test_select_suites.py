"""tools/select_suites.py : sélection des suites d'après l'index Git, sur un dépôt temporaire. Aucun test réel n'est lancé.

    python3 -m unittest discover -s tests/select_suites -v
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from select_suites import selectionner, suites_npm  # noqa: E402

SELECTEUR = Path(__file__).resolve().parents[2] / "tools" / "select_suites.py"
LANCEUR = '#!/bin/bash\n: lanceur factice\nSUITES_NPM=(mothra:mothra)\n'
LISTE_SHELL = ('# suites shell\n\ntests/finish_branch/test_finish_branch.sh finish_branch bash\n'
               'tests/hooks/test_pre_commit.sh hooks sh   # raison\n')
GARDES = {"identifiants_personnels", "secret_scan"}   # gardes toujours sélectionnées (secret_scan : pre-commit-secret-scan, D7)


class Selecteur(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "test")
        self.ecrire("tests/run_all.sh", LANCEUR)
        self.ecrire("tests/suites_shell.txt", LISTE_SHELL)
        self.ecrire("tests/alpha/test_alpha.py", "import outil_a\nCOMMANDE = '.claude/commands/demo.md'\n")   # nomme tools/outil_a.py
        self.ecrire("tests/beta/test_beta.py", "CHEMIN = 'tools/sous/outil_b.py'\n")      # nomme un chemin
        self.ecrire("tests/identifiants_personnels/test_id.py", "pass\n")
        self.ecrire("tests/secret_scan/test_secrets.py", "pass\n")
        self.ecrire("tests/hooks/test_pre_commit.sh", "echo hooks\n")
        self.ecrire("tests/finish_branch/test_finish_branch.sh", "echo finish\n")
        self.ecrire("tests/gamma/test_gamma.py", "DONNEES = 'cas.yaml'\n")
        self.ecrire("tests/manual/test_manuel.py", "pass\n")
        self.ecrire("tests/composants/test_composants.py", "pass\n")
        self.ecrire("tests/flow_views/test_flow_views.py", "pass\n")
        self.ecrire("tests/mothra_consignes/test_consignes.py", "CHEMIN = 'mothra/CLAUDE.md'\n")   # nomme un chemin de Mothra
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout

    def ecrire(self, relatif, texte="x\n"):
        chemin = self.racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte)

    def indexer(self, *relatifs, texte="y\n"):
        for relatif in relatifs:
            self.ecrire(relatif, texte)
        self.git("add", "-A")

    def desindexer(self, relatif):
        """Retire un fichier de l'index et du disque (entre deux cas d'un même test)."""
        self.git("reset", "-q")
        (self.racine / relatif).unlink()

    def selection(self):
        resultat = subprocess.run([sys.executable, str(SELECTEUR), "--root", str(self.racine)], capture_output=True, text=True)
        return resultat.returncode, resultat.stdout

    def suites(self):
        code, sortie = self.selection()
        self.assertEqual(code, 0, sortie)
        return {ligne.split(" : ")[1] for ligne in sortie.splitlines()}

    def test_outil_nomme_par_une_suite(self):
        self.indexer("tools/outil_a.py")
        self.assertEqual(self.suites(), {"alpha", "manual", *GARDES})

    def test_chaque_ligne_donne_la_raison(self):
        self.indexer("tools/outil_a.py")
        code, sortie = self.selection()
        self.assertIn("select_suites : alpha : tools/outil_a.py (« outil_a » nommé par ses tests)", sortie)
        self.assertIn("select_suites : identifiants_personnels : toujours sélectionnée", sortie)

    def test_chemin_complet_nomme(self):
        self.indexer("tools/sous/outil_b.py")
        self.assertEqual(self.suites(), {"beta", *GARDES})

    def test_fichier_de_donnees_nomme_par_son_nom(self):
        self.indexer("tests/postures/cas.yaml")
        self.assertEqual(self.suites(), {"gamma", *GARDES})

    def test_chemin_dans_une_suite(self):
        self.indexer("tests/alpha/test_alpha.py")
        self.assertEqual(self.suites(), {"alpha", *GARDES})

    def test_script_de_test_shell_liste(self):
        self.indexer("tests/hooks/test_pre_commit.sh")
        self.assertEqual(self.suites(), {"hooks", *GARDES})

    def test_script_de_test_shell_de_la_liste_de_donnees_donne_sa_suite(self):
        # R-130 : la liste est tests/suites_shell.txt (commentaire de fin de ligne permis), pas le texte du lanceur
        self.indexer("tests/finish_branch/test_finish_branch.sh")
        self.assertEqual(self.suites(), {"finish_branch", *GARDES})

    def test_script_de_test_shell_absent_de_la_liste_exige_l_execution_complete(self):
        self.indexer("tests/inconnu/test_inconnu.sh")
        self.assertEqual(self.selection()[0], 3)

    def test_la_liste_des_suites_shell_exige_l_execution_complete(self):
        self.indexer("tests/suites_shell.txt", texte="# autre\n")
        code, sortie = self.selection()
        self.assertEqual(code, 3, sortie)
        self.assertIn("tests/suites_shell.txt", sortie)

    def test_liste_des_suites_shell_mal_formee_code_2_avec_le_numero_de_ligne(self):
        for ligne in ("tests/hooks/test_x.sh hooks", "tests/hooks/test_x.sh hooks fish", "hooks/test_x.sh hooks sh",
                      "tests/hooks/test_x.sh hooks sh extra"):
            with self.subTest(ligne=ligne):
                self.ecrire("tests/suites_shell.txt", f"# en-tête\n\n{ligne}\n")
                self.git("add", "-A")
                resultat = subprocess.run([sys.executable, str(SELECTEUR), "--root", str(self.racine)], capture_output=True, text=True)
                self.assertEqual(resultat.returncode, 2, resultat.stdout)
                self.assertIn("tests/suites_shell.txt, ligne 3 mal formée", resultat.stderr)

    def test_liste_des_suites_shell_triee_dans_le_depot(self):
        racine = Path(__file__).resolve().parents[2]
        chemins = [l.split()[0] for l in (racine / "tests" / "suites_shell.txt").read_text(encoding="utf-8").splitlines()
                   if l.split("#", 1)[0].strip()]
        self.assertEqual(chemins, sorted(chemins))

    # mothra-slices, groupe 3, design D10 : la suite npm, déclarée par la ligne SUITES_NPM de tests/run_all.sh, et les chemins de Mothra et du contrat.
    def test_fichier_typescript_du_serveur_selectionne_la_suite_npm_seule(self):
        self.indexer("mothra/server/src/routes/vues.ts")
        code, sortie = self.selection()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.suites(), {"mothra", *GARDES})   # ni exécution complète, ni suite du manuel
        self.assertIn("select_suites : mothra : mothra/server/src/routes/vues.ts (chemin sous mothra/)", sortie)

    def test_tout_chemin_sous_mothra_selectionne_la_suite_npm(self):
        for chemin in ("mothra/package.json", "mothra/front/test/x.test.ts", "mothra/front/x.tsx", "mothra/.npmrc"):
            with self.subTest(chemin=chemin):
                self.indexer(chemin)
                self.assertEqual(self.suites(), {"mothra", *GARDES})
                self.desindexer(chemin)

    def test_un_chemin_de_mothra_autre_que_typescript_ajoute_les_suites_que_ses_tests_nomment(self):
        self.indexer("mothra/CLAUDE.md")
        code, sortie = self.selection()
        self.assertEqual(code, 0, sortie)   # jamais l'exécution complète
        self.assertEqual(self.suites(), {"mothra", "mothra_consignes", *GARDES})

    def test_un_fichier_typescript_nomme_par_une_suite_reste_la_suite_npm_seule(self):
        self.ecrire("tests/mothra_consignes/test_ts.py", "CHEMIN = 'x.ts'\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "nomme")
        self.indexer("mothra/server/x.ts")
        self.assertEqual(self.suites(), {"mothra", *GARDES})

    def test_le_verrou_npm_et_le_fichier_de_version_selectionnent_aussi_les_composants(self):
        for chemin in ("mothra/package-lock.json", "mothra/.node-version"):
            with self.subTest(chemin=chemin):
                self.indexer(chemin)
                self.assertEqual(self.suites(), {"mothra", "composants", *GARDES})
                self.desindexer(chemin)

    def test_contrats_de_vues_de_parite_et_schemas_selectionnent_la_suite_npm_et_flow_views(self):
        for chemin in ("contrats/vues.json", "contrats/cas-parite.json", "contrats/cas-masquage.json", "contrats/schemas/cellule.schema.json"):
            with self.subTest(chemin=chemin):
                self.indexer(chemin)
                self.assertEqual(self.suites(), {"mothra", "flow_views", *GARDES})
                self.desindexer(chemin)

    def test_l_oracle_de_masquage_est_une_suite_sans_base_choisie_par_flow_views_et_par_ses_fichiers(self):
        # tests/oracle_masquage (R-20261104-20) : suite sans base, ses tests nomment flow_views ; elle est choisie par tools/flow_views.py
        # (« flow_views » nommé par ses tests) et par ses propres fichiers (chemin dans la suite).
        self.ecrire("tests/oracle_masquage/test_oracle_propagation.py", "import flow_views as fv\n")
        self.ecrire("tests/oracle_masquage/oracle_masquage.py", "pass\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "suite oracle")
        for chemin in ("tools/flow_views.py", "tests/oracle_masquage/oracle_masquage.py", "tests/oracle_masquage/test_oracle_propagation.py"):
            with self.subTest(chemin=chemin):
                self.indexer(chemin)
                self.assertIn("oracle_masquage", self.suites())
                if chemin.startswith("tests/"):
                    self.git("reset", "-q")
                    self.git("checkout", "--", chemin)   # fichier déjà commité : remis en l'état pour le cas suivant
                else:
                    self.desindexer(chemin)

    def test_un_autre_fichier_du_dossier_des_contrats_n_est_pas_cartographie(self):
        self.indexer("contrats/glossaire.json")   # tranche 1 : pas encore cartographié, donc exécution complète
        code, sortie = self.selection()
        self.assertEqual(code, 3, sortie)
        self.assertIn("contrats/glossaire.json", sortie)

    def test_un_chemin_cartographie_ne_declenche_jamais_l_execution_complete(self):
        self.indexer("mothra/server/src/db/pool.ts", "mothra/package-lock.json", "contrats/vues.json")
        code, sortie = self.selection()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("exécution complète", sortie)

    def test_sans_la_ligne_suites_npm_un_chemin_de_mothra_exige_l_execution_complete(self):
        self.ecrire("tests/run_all.sh", LANCEUR.replace("SUITES_NPM=(mothra:mothra)\n", ""))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "sans ligne")
        self.indexer("mothra/server/src/x.ts")
        code, sortie = self.selection()
        self.assertEqual(code, 3, sortie)
        self.assertIn("mothra/server/src/x.ts", sortie)

    def test_un_changement_du_lanceur_exige_l_execution_complete(self):
        self.indexer("tests/run_all.sh", texte=LANCEUR + "SUITES_NPM=(mothra:mothra autre:autre)\n")
        code, sortie = self.selection()
        self.assertEqual(code, 3, sortie)
        self.assertIn("tests/run_all.sh", sortie)

    def test_entree_mal_formee_de_suites_npm_code_2_avec_le_numero_d_entree(self):
        for entree in ("mothra", "mothra:", "../mothra:mothra", "mothra:mo:thra"):
            with self.subTest(entree=entree):
                self.ecrire("tests/run_all.sh", f"#!/bin/bash\nSUITES_NPM=(mothra:mothra {entree})\n")
                self.git("add", "-A")
                resultat = subprocess.run([sys.executable, str(SELECTEUR), "--root", str(self.racine)], capture_output=True, text=True)
                self.assertEqual(resultat.returncode, 2, resultat.stdout)
                self.assertIn("tests/run_all.sh, SUITES_NPM, entrée 2 mal formée", resultat.stderr)

    def test_le_nom_de_la_suite_npm_est_celui_de_la_ligne(self):
        self.ecrire("tests/run_all.sh", "#!/bin/bash\nSUITES_NPM=(mothra:interface)\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "ligne")
        self.indexer("mothra/front/x.ts")
        self.assertEqual(self.suites(), {"interface", *GARDES})

    def test_la_ligne_du_depot_est_lue_par_le_selecteur(self):
        racine = Path(__file__).resolve().parents[2]
        self.assertEqual(suites_npm(racine), {"mothra": "mothra"})

    def test_la_fonction_d_ecriture_du_referentiel_selectionne_sa_suite_dans_le_depot(self):
        # change cycle-referential-schema, tâche 2.1 : tools/flow_referential.py est cartographié par le texte des tests de tests/flow_referential
        # (règle générale « nommé par ses tests »), sans entrée dans le sélecteur ; le dépôt réel est lu, aucun test n'est lancé
        racine = Path(__file__).resolve().parents[2]
        raisons, complets = selectionner(racine, ["tools/flow_referential.py"])
        self.assertEqual(complets, [])
        self.assertIn("flow_referential", raisons)

    def test_manuel_seul_selectionne_la_suite_du_manuel(self):
        self.indexer("docs/pmzilla/manuel.md")
        self.assertEqual(self.suites(), {"manual", *GARDES})

    def test_autre_documentation_ne_selectionne_pas_la_suite_du_manuel(self):
        self.indexer("docs/pmzilla/autre.md", "README.md")
        self.assertEqual(self.suites(), {*GARDES})

    def test_script_de_tools_nomme_selectionne_aussi_la_suite_du_manuel(self):
        self.indexer("tools/outil_a.py")
        self.assertEqual(self.suites(), {"alpha", "manual", *GARDES})

    def test_script_shell_de_tools_selectionne_la_suite_du_manuel(self):
        self.indexer("tools/outil_a.sh")
        self.assertEqual(self.suites(), {"alpha", "manual", *GARDES})

    def test_commande_slash_selectionne_la_suite_du_manuel(self):
        self.indexer(".claude/commands/demo.md")
        self.assertEqual(self.suites(), {"alpha", "manual", *GARDES})

    def test_la_raison_de_la_suite_du_manuel_est_donnee(self):
        self.indexer(".claude/commands/demo.md")
        self.assertIn("select_suites : manual : .claude/commands/demo.md", self.selection()[1])

    def test_commande_slash_que_aucun_test_ne_nomme_exige_l_execution_complete(self):
        self.indexer(".claude/commands/inconnue.md")
        self.assertEqual(self.selection()[0], 3)

    def test_script_de_tools_qu_aucun_test_ne_nomme_exige_toujours_l_execution_complete(self):
        self.indexer("tools/orphelin.py")
        code, sortie = self.selection()
        self.assertEqual(code, 3)
        self.assertIn("exécution complète requise : tools/orphelin.py", sortie)

    def test_le_manuel_ne_compte_pas_comme_suite_du_chemin_pour_un_script_orphelin(self):
        self.indexer("tools/orphelin.sh", "docs/pmzilla/manuel.md")
        self.assertEqual(self.selection()[0], 3)

    def test_un_script_hors_de_tools_ne_selectionne_pas_la_suite_du_manuel(self):
        self.indexer("tools/sous/outil_b.py")
        self.assertEqual(self.suites(), {"beta", *GARDES})

    def test_documentation_seule_ne_selectionne_que_les_gardes(self):
        self.indexer("docs/pmzilla/x.md", "openspec/changes/c/tasks.md", "CHANGELOG.md", "README.md", "_bmad-output/pmzilla/a.md")
        self.assertEqual(self.suites(), {*GARDES})

    def test_fichier_de_code_inconnu_exige_l_execution_complete(self):
        self.indexer("tools/orphelin.py")
        code, sortie = self.selection()
        self.assertEqual(code, 3)
        self.assertIn("select_suites : exécution complète requise : tools/orphelin.py", sortie)

    def test_fichiers_sensibles_exigent_l_execution_complete(self):
        for chemin in ("CLAUDE.md", ".claude/settings.json", "tests/run_all.sh", "tools/hooks/pre-commit", "tools/hooks/pre-push",
                       "tools/select_suites.py"):
            with self.subTest(chemin=chemin):
                self.git("reset", "-q")
                self.indexer(chemin, texte="z\n")
                code, sortie = self.selection()
                self.assertEqual(code, 3, sortie)
                self.assertIn(chemin, sortie)

    def test_modules_importes_par_le_crochet_exigent_l_execution_complete(self):
        # pre-commit-secret-scan, D7 : le module des secrets et celui des noms, importés par le crochet pre-commit, comptent comme le crochet
        # fix/sorties-et-masquage : l'outil des noms des messages, lancé par commit-msg et pre-push, aussi
        for chemin in ("tools/secret_scan.py", "tools/sensitive_names.py", "tools/commit_names_scan.py"):
            with self.subTest(chemin=chemin):
                self.git("reset", "-q")
                self.indexer(chemin, texte="z\n")
                code, sortie = self.selection()
                self.assertEqual(code, 3, sortie)
                self.assertIn(chemin, sortie)

    def test_garde_des_secrets_toujours_selectionnee_avec_sa_raison(self):
        self.indexer("docs/pmzilla/x.md")
        code, sortie = self.selection()
        self.assertEqual(code, 0, sortie)
        self.assertIn("select_suites : secret_scan : toujours sélectionnée : parcourt tous les fichiers suivis", sortie)

    def test_fichier_supprime(self):
        self.indexer("tests/alpha/test_alpha_bis.py", texte="pass\n")
        self.git("commit", "-q", "-m", "bis")
        self.git("rm", "-q", "tests/alpha/test_alpha_bis.py")
        self.assertEqual(self.suites(), {"alpha", *GARDES})

    def test_suppression_du_dernier_test_d_une_suite_exige_l_execution_complete(self):
        self.git("rm", "-q", "tests/alpha/test_alpha.py")
        self.assertEqual(self.selection()[0], 3)

    def test_fichier_supprime_inconnu_exige_l_execution_complete(self):
        self.indexer("tools/ancien.py")
        self.git("commit", "-q", "-m", "ajout")
        self.git("rm", "-q", "tools/ancien.py")
        self.assertEqual(self.selection()[0], 3)

    def test_fichier_renomme_compte_les_deux_chemins(self):
        self.indexer("tools/outil_a.py")
        self.git("commit", "-q", "-m", "ajout")
        self.git("mv", "tools/outil_a.py", "tools/orphelin.py")
        code, sortie = self.selection()
        self.assertEqual(code, 3)
        self.assertIn("tools/orphelin.py", sortie)

    def test_un_chemin_inconnu_l_emporte_sur_les_autres(self):
        self.indexer("tools/outil_a.py", "tools/orphelin.py")
        code, sortie = self.selection()
        self.assertEqual(code, 3)
        self.assertNotIn("alpha", sortie)

    def test_index_vide_ne_selectionne_que_les_gardes(self):
        self.assertEqual(self.suites(), {*GARDES})

    def test_aucun_fichier_ecrit(self):
        self.indexer("tools/outil_a.py")
        avant = sorted(str(p.relative_to(self.racine)) for p in self.racine.rglob("*") if ".git" not in p.parts)
        etat = self.git("status", "--porcelain")
        self.selection()
        apres = sorted(str(p.relative_to(self.racine)) for p in self.racine.rglob("*") if ".git" not in p.parts)
        self.assertEqual(avant, apres)
        self.assertEqual(etat, self.git("status", "--porcelain"))

    def test_hors_depot_git_code_2(self):
        vide = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, vide, True)
        resultat = subprocess.run([sys.executable, str(SELECTEUR), "--root", str(vide)], capture_output=True, text=True)
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("select_suites : pas un dépôt Git", resultat.stderr)

    def test_usage(self):
        resultat = subprocess.run([sys.executable, str(SELECTEUR), "--inconnue"], capture_output=True, text=True)
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("select_suites : usage", resultat.stderr)


class LecteursOpenspec(unittest.TestCase):
    """Option --openspec-readers (light-spec-finish, D6, question Q10) : la règle (a) et la liste déclarée tests/openspec_readers.txt."""
    git = Selecteur.git
    ecrire = Selecteur.ecrire
    indexer = Selecteur.indexer

    def setUp(self):
        Selecteur.setUp(self)
        self.liste_declaree("# lecteurs déclarés\n")

    def liste_declaree(self, texte):
        self.ecrire("tests/openspec_readers.txt", texte)

    def lecteurs(self, *supplement):
        return subprocess.run([sys.executable, str(SELECTEUR), "--openspec-readers", "--root", str(self.racine), *supplement],
                              capture_output=True, text=True)

    def liste(self):
        resultat = self.lecteurs()
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        return {ligne.split(" : ")[1]: ligne for ligne in resultat.stdout.splitlines()}

    def test_regle_a_garde_toujours_listee(self):
        self.assertEqual(set(self.liste()), {*GARDES})

    def test_regle_a_donne_sa_raison(self):
        self.assertEqual(self.liste()["identifiants_personnels"], "select_suites : identifiants_personnels : garde toujours sélectionnée")

    def test_regle_a_garde_des_secrets(self):
        self.assertEqual(self.liste()["secret_scan"], "select_suites : secret_scan : garde toujours sélectionnée")

    def test_liste_declaree_donne_les_suites_et_la_raison(self):
        self.liste_declaree("# lecteurs\n\ndelta\nalpha  # lit la configuration\n")
        liste = self.liste()
        self.assertEqual(set(liste), {*GARDES, "delta", "alpha"})
        self.assertEqual(liste["delta"], "select_suites : delta : déclarée (tests/openspec_readers.txt)")
        self.assertEqual(liste["alpha"], "select_suites : alpha : déclarée (tests/openspec_readers.txt)")

    def test_une_suite_qui_nomme_openspec_sans_etre_declaree_n_est_pas_listee(self):
        self.indexer("tests/delta/test_delta.py", texte="CHEMIN = 'openspec/changes/x/tasks.md'\n")
        self.indexer("tools/outil_a.py", texte="DOSSIER = 'openspec'\n")
        self.indexer("tests/finish_branch/test_finish_branch.sh", texte="mkdir -p openspec/changes\n")
        self.assertEqual(set(self.liste()), {*GARDES})

    def test_une_exemption_n_est_pas_listee(self):
        self.liste_declaree("alpha\n!beta : liste les fichiers suivis mais ne garde que tools/\n")
        self.assertEqual(set(self.liste()), {*GARDES, "alpha"})

    def test_garde_declaree_deux_fois_garde_la_raison_de_la_regle_a(self):
        self.liste_declaree("identifiants_personnels\n")
        self.assertEqual(self.liste()["identifiants_personnels"], "select_suites : identifiants_personnels : garde toujours sélectionnée")

    def test_fichier_de_liste_absent_code_2(self):
        (self.racine / "tests" / "openspec_readers.txt").unlink()
        resultat = self.lecteurs()
        self.assertEqual(resultat.returncode, 2)
        self.assertEqual(resultat.stdout, "")
        self.assertIn("openspec_readers.txt", resultat.stderr)

    def test_ligne_mal_formee_ou_en_double_code_2(self):
        for texte in ("alpha extra\n", "!alpha\n", "alpha\nalpha\n", "alpha\n!alpha : raison\n"):
            self.liste_declaree(texte)
            resultat = self.lecteurs()
            self.assertEqual(resultat.returncode, 2, texte)
            self.assertEqual(resultat.stdout, "", texte)

    def test_ne_lit_pas_l_index_et_ne_sort_jamais_3(self):
        self.indexer("CLAUDE.md", "tools/inconnu.bin")       # des chemins qui exigeraient l'exécution complète
        resultat = self.lecteurs()
        self.assertEqual(resultat.returncode, 0)
        self.assertNotIn("exécution complète", resultat.stdout)

    def test_aucun_fichier_ecrit(self):
        etat = self.git("status", "--porcelain")
        self.lecteurs()
        self.assertEqual(etat, self.git("status", "--porcelain"))

    def test_hors_depot_git_code_2(self):
        vide = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, vide, True)
        resultat = subprocess.run([sys.executable, str(SELECTEUR), "--openspec-readers", "--root", str(vide)], capture_output=True, text=True)
        self.assertEqual(resultat.returncode, 2)

    def test_usage(self):
        self.assertEqual(self.lecteurs("extra").returncode, 2)
        resultat = subprocess.run([sys.executable, str(SELECTEUR), "--openspec-readers", "--root"], capture_output=True, text=True)
        self.assertEqual(resultat.returncode, 2)


class PackageJsonDeMothra(unittest.TestCase):
    """R-20261101-02 (Q137) : package.json d'un sous-dossier de mothra/ = chemin complet + cartographie ; mothra/package.json = recherche par nom."""
    git, ecrire, indexer, selection, suites = (Selecteur.git, Selecteur.ecrire, Selecteur.indexer, Selecteur.selection, Selecteur.suites)

    def setUp(self):
        Selecteur.setUp(self)
        self.ecrire("tests/run_all/test_run_all.py", "pass\n")
        self.ecrire("tests/lecteur_nom/test_lecteur.py", "NOM = 'package.json'\n")                  # nomme package.json sans chemin
        self.ecrire("tests/lecteur_chemin/test_lecteur.py", "CHEMIN = 'mothra/front/package.json'\n")   # nomme le chemin complet
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "suites du package.json")

    def test_sous_paquet_chemin_complet_et_cartographie_sans_recherche_par_nom(self):
        self.indexer("mothra/front/package.json")
        code, sortie = self.selection()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.suites(), {"mothra", "run_all", "composants", "lecteur_chemin", *GARDES})
        self.assertIn("select_suites : run_all : mothra/front/package.json (package.json d'un sous-paquet de Mothra (cartographie))", sortie)

    def test_chaque_sous_paquet_est_traite_de_meme(self):
        for chemin in ("mothra/contract/package.json", "mothra/server/package.json"):
            with self.subTest(chemin=chemin):
                self.indexer(chemin)
                self.assertEqual(self.selection()[0], 0)
                self.assertEqual(self.suites(), {"mothra", "run_all", "composants", *GARDES})
                self.git("reset", "-q")
                (self.racine / chemin).unlink()

    def test_chemin_plus_profond_garde_la_recherche_par_nom(self):
        self.indexer("mothra/front/a/package.json")
        self.assertEqual(self.selection()[0], 0)
        self.assertEqual(self.suites(), {"mothra", "lecteur_nom", "lecteur_chemin", *GARDES})

    def test_racine_de_mothra_garde_la_recherche_par_nom(self):
        self.indexer("mothra/package.json")
        self.assertEqual(self.suites(), {"mothra", "lecteur_nom", "lecteur_chemin", *GARDES})   # la recherche par nom trouve les deux


if __name__ == "__main__":
    unittest.main()
