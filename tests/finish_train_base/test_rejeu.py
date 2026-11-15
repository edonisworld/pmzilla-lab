"""
Groupes 3.5 et 3.6 (change targeted-suites-admission, design D5, D9) : runner rouge sur l'arbre intégré, indice des branches qui ont sélectionné la suite
rouge, rejeu unique des suites rouges sur le sommet du train, et ligne du défaut de sélection. Puis 12.3 de ci-local-runner (D9, R-20261101-114) : les
suites rouges viennent du passage du conteneur (phase portable, rejeu par --rejeu, FINISH_TRAIN_CI) ou de la passe Mac (rejeu par le runner).

Vrais enfants : finish_train.sh du dossier d'exécution jetable, le VRAI tools/select_suites.py (copié dans main du dépôt jetable avec des suites
factices tests/suite_a, suite_b, suite_c), Git, bash. Faux déclarés : un faux passage du conteneur à lui (« ci neuf » ; journal ci-appels, FAKE_ROUGES, FAKE_REJEU_CODE)
et un faux runner Mac à lui (« runner neuf », FAKE_ROUGES_MAC) ; le faux matin et le faux git espion de l'aide commune. Risque non couvert : le vrai runner filtré (écriture d'empreinte, garde du code 8), couvert par tests/run_all.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, OUTILS  # noqa: E402

RUNNER_NEUF = """#!/bin/bash
# passe Mac (FINISH_TRAIN_RUNNER) : sans nom de suite = la passe --mac, rouge avec FAKE_ROUGES_MAC si elle est posée ; avec des noms = le rejeu Mac
ETAT="@ETAT@"
echo "runner-neuf pwd=$(pwd -P) args=[$*] jeton=${FINISH_LOCK_TOKEN:+present}" >> "$ETAT/appels.log"
noms=0
for argument in "$@"; do
  case "$argument" in --*) ;; *) noms=1 ;; esac
done
if [ "$noms" -eq 0 ]; then
  if [ -n "${FAKE_ROUGES_MAC:-}" ]; then
    echo "TOTAL : 3 tests dans 2 suites · 1 suite(s) en échec : $FAKE_ROUGES_MAC · durée totale 1 s"
    exit 1
  fi
  echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"
  exit 0
fi
for argument in "$@"; do
  case "$argument" in --*) if [ -n "${FAKE_RUNNER_ECRIVAIN:-}" ]; then echo "$argument" >> "$ETAT/ecrit.log"; fi ;; esac
done
echo "TOTAL : 1 tests dans 1 suites · tous réussis · durée totale 1 s"
exit "${FAKE_REJEU_CODE:-1}"
"""
# passage du conteneur (FINISH_TRAIN_CI), noms de la convention commune : journal $ETAT/ci-appels (arguments), code et lignes pilotés par variables.
# Sans --rejeu : rouge en phase portable avec FAKE_ROUGES si elle est posée (phases suivantes sautées), sinon vert. Avec --rejeu : sort FAKE_REJEU_CODE.
CI_NEUF = """#!/bin/bash
ETAT="@ETAT@"
echo "$*" >> "$ETAT/ci-appels"
echo "ci-neuf pwd=$(pwd -P) args=[$*] jeton=${FINISH_LOCK_TOKEN:+present}" >> "$ETAT/appels.log"
rejeu=0
for argument in "$@"; do
  case "$argument" in
    --rejeu) rejeu=1 ;;
    --*) if [ -n "${FAKE_RUNNER_ECRIVAIN:-}" ]; then echo "$argument" >> "$ETAT/ecrit.log"; fi ;;
  esac
done
if [ "$rejeu" -eq 1 ]; then
  echo "TOTAL : 1 tests dans 1 suites · tous réussis · durée totale 1 s"
  # la ligne que ci_local écrit pour un rejeu rouge (tools/ci_local.sh, tranche 2) : sans elle, le code 1 n'est pas « suite rouge reproduite »
  if [ "${FAKE_REJEU_CODE:-1}" = 1 ] && [ -z "${FAKE_REJEU_SANS_LIGNE:-}" ]; then
    echo "ci_local : rejeu rouge (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb) : suites"
  fi
  exit "${FAKE_REJEU_CODE:-1}"
fi
if [ -n "${FAKE_PORTABLE_ROUGE_SANS_SUITE:-}" ]; then
  echo "ci_passage : phase portable : rouge · 3 s"
  echo "ci_passage : phase base : sautée (phase précédente rouge)"
  echo "ci_passage : phase e2e : sautée (phase précédente rouge)"
  echo "ci_local : verdict rouge (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb)"
  exit 1
fi
if [ -n "${FAKE_ROUGES:-}" ]; then
  echo "TOTAL : 3 tests dans 2 suites · 1 suite(s) en échec : $FAKE_ROUGES · durée totale 1 s"
  echo "ci_passage : phase portable : rouge · 3 s : $FAKE_ROUGES"
  echo "ci_passage : phase base : sautée (phase précédente rouge)"
  echo "ci_passage : phase e2e : sautée (phase précédente rouge)"
  echo "ci_local : verdict rouge (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb) : $FAKE_ROUGES"
  exit 1
fi
echo "ci_passage : phase portable : verte · 1 s"
echo "ci_passage : phase base : verte · 1 s"
echo "ci_passage : phase e2e : verte · 1 s"
echo "ci_local : verdict vert (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb, 3 suites, 0 suites Mac non lancées)"
exit 0
"""
HINT_PREFIX = "finish_train : train rouge : suites rouges sélectionnées par"
DEFAUT = "finish_train : défaut de sélection : suites rouges hors de toute sélection de select_suites"
LIGNE_70 = "finish_train : retirer de la liste la branche qui casse ces suites, puis relancer la ligne"
BANNIERE = "===== fin du train"


class Rejeu(AvecTrain):
    def setUp(self):
        super().setUp()
        t = self.t
        self.runner_neuf = t.poser(t.fakes / "runner_neuf.sh", RUNNER_NEUF)
        self.ci_neuf = t.poser(t.fakes / "ci_neuf.sh", CI_NEUF)
        t.commit_main({"tools/select_suites.py": (OUTILS / "select_suites.py").read_text(encoding="utf-8"),
                       "tests/suite_a/test_a.py": "import outil_a\n", "tests/suite_b/test_b.py": "import outil_b\n",
                       "tests/suite_c/test_c.py": "import outil_c\n"}, "sélecteur et suites factices", pousser=True)
        t.mettre_a_jour_run()
        for lettre in "abc":
            t.branche(f"feat/{lettre}", {f"tools/outil_{lettre}.sh": f"{lettre}\n"})

    def env(self, rouges, rejeu, **extra):
        return {"FINISH_TRAIN_CI": f"bash {self.ci_neuf}", "FINISH_TRAIN_RUNNER": f"bash {self.runner_neuf}", "FAKE_ROUGES": rouges,
                "FAKE_REJEU_CODE": str(rejeu), **extra}

    def lancer(self, noms, rouges, rejeu, entree="o\n", **extra):
        """Suites rouges de la phase portable du conteneur (rejeu par --rejeu du passage du conteneur, D9)."""
        return self.t.lance(*noms, extra=self.env(rouges, rejeu, **extra), entree=entree)

    def lancer_mac(self, noms, rouges, rejeu, entree="o\n", **extra):
        """Conteneur vert, suites rouges à la passe --mac (rejeu par le runner, D9)."""
        return self.t.lance(*noms, extra=self.env("", rejeu, FAKE_ROUGES_MAC=rouges, **extra), entree=entree)

    def lignes(self, r):
        return r.texte.splitlines()

    def ci_appels(self):
        fichier = self.t.etat / "ci-appels"
        return fichier.read_text(encoding="utf-8").splitlines() if fichier.exists() else []

    def rejeus_ci(self):
        return [l for l in self.ci_appels() if "--rejeu" in l.split()]

    @staticmethod
    def noms_du_rejeu(ligne):
        """Arguments après --rejeu, sans le mot « portable » éventuel (Q220 : `--rejeu portable <suites>` ; D9 : `--rejeu <suites>`)."""
        apres = ligne.split("--rejeu", 1)[1].split()
        return apres[1:] if apres[:1] == ["portable"] else apres

    def test_rouge_puis_vert_au_rejeu_donne_71_et_son_texte(self):
        avant = self.t.instantane()
        r = self.lancer(["feat/a", "feat/b"], "suite_a", 0)
        self.code(r, 71, "runner non concluant : suites rouges non reproduites (suite_a) ; rien n'est fusionné")
        self.absent(r, "train rouge : suites en échec", LIGNE_70, DEFAUT)
        self.contient(r, f"{HINT_PREFIX} : feat/a")
        self.rien_ne_change(avant)

    def test_rouge_au_rejeu_donne_70_avec_les_lignes_d_avant(self):
        avant = self.t.instantane()
        r = self.lancer(["feat/a", "feat/b"], "suite_a", 1)
        self.code(r, 70, "train rouge : suites en échec : suite_a ; rien n'est fusionné",
                  "retirer de la liste la branche qui casse ces suites, puis relancer la ligne")
        self.absent(r, "suites rouges non reproduites")
        self.rien_ne_change(avant)

    def test_tout_autre_code_du_rejeu_du_conteneur_donne_71(self):
        # réécrit (revue croisée tranche 2, R-20261101-116) : le 70 « suite rouge reproduite » exige le code 1 ET la ligne « ci_local : rejeu rouge » ;
        # les codes 2, 3, 4, 5, 7 du rejeu du conteneur sont un conteneur non concluant (71), plus strict qu'avant (où tout code non nul donnait 70)
        for code in (2, 3, 4, 5, 7):
            with self.subTest(code=code):
                r = self.lancer(["feat/a"], "suite_a", code)
                self.code(r, 71, f"runner non concluant : rejeu du conteneur non concluant (code {code}) ; rien n'est fusionné")
                self.absent(r, "train rouge : suites en échec", LIGNE_70)

    def test_code_1_du_rejeu_sans_la_ligne_de_rejeu_rouge_donne_71(self):
        r = self.lancer(["feat/a"], "suite_a", 1, FAKE_REJEU_SANS_LIGNE="1")
        self.code(r, 71, "runner non concluant : rejeu du conteneur non concluant (code 1) ; rien n'est fusionné")
        self.absent(r, "train rouge : suites en échec", LIGNE_70)

    def test_phase_portable_rouge_sans_suite_nommee_donne_71_sans_rejeu(self):
        # Q235 (R-20261101-119), refus 71 de finish_train.sh : une ligne de phase portable rouge qui ne nomme aucune suite n'a rien à rejouer
        avant = self.t.instantane()
        r = self.t.lance("feat/a", extra={"FINISH_TRAIN_CI": f"bash {self.ci_neuf}", "FINISH_TRAIN_RUNNER": f"bash {self.runner_neuf}",
                                          "FAKE_ROUGES": "", "FAKE_PORTABLE_ROUGE_SANS_SUITE": "1"}, entree="o\n")
        self.code(r, 71, "runner non concluant : phase portable du conteneur rouge sans suite nommée (aucune) ; rien n'est fusionné")
        self.assertEqual(self.rejeus_ci(), [], "aucun rejeu sans suite nommée")
        self.assertEqual(len(self.ci_appels()), 1)
        self.assertEqual(self.t.appels("runner-neuf"), [], "la passe Mac n'est pas lancée")
        self.rien_ne_change(avant)

    def test_le_rejeu_lance_le_passage_du_conteneur_avec_les_noms_dans_le_worktree_d_integration(self):
        self.lancer(["feat/a", "feat/b"], "suite_a suite_b", 1)
        complet, rejeu = self.t.appels("ci-neuf")
        self.assertNotIn("--rejeu", complet)
        self.assertIn("--rejeu", rejeu)
        self.assertEqual(self.noms_du_rejeu(rejeu.split("args=[", 1)[1].split("]")[0]), ["suite_a", "suite_b"])
        self.assertIn("/wt-train-", rejeu)
        self.assertIn("jeton=present", rejeu)
        self.assertEqual(len(self.ci_appels()), 2, "un seul rejeu")
        self.assertEqual(len(self.rejeus_ci()), 1)
        self.assertEqual(self.t.appels("runner-neuf"), [], "le conteneur rouge arrête la porte avant la passe Mac")

    def test_pas_de_rejeu_a_l_essai(self):
        r = self.t.lance("--essai", "feat/a", extra=self.env("suite_a", 0))
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.appels("runner-neuf"), [], "l'essai n'a lancé ni runner ni rejeu")
        self.assertEqual(self.ci_appels(), [], "l'essai n'a lancé ni passage du conteneur ni rejeu")
        self.absent(r, HINT_PREFIX)

    def test_le_passage_du_conteneur_puis_la_passe_mac_tournent_meme_quand_chaque_branche_a_une_empreinte_de_branche(self):
        for lettre in "ab":
            wt = self.t.dossier_worktree(f"feat/{lettre}")
            fichier = Path(self.t.git("rev-parse", "--path-format=absolute", "--git-path", "pmzilla-run-branch-ok", cwd=wt))
            fichier.write_text(f"{self.t.git('rev-parse', 'HEAD^{tree}', cwd=wt)}\tsuite_{lettre}\n", encoding="utf-8")
        r = self.t.lance("feat/a", "feat/b", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        (ligne,) = self.t.appels("runner pwd")
        self.assertIn("args=[]", ligne)   # la passe Mac complète, sans nom de suite : FINISH_TRAIN_RUNNER est posée par le test et remplace la commande entière (aucun --mac ajouté)
        self.assertIn("/wt-train-", ligne)
        (ci,) = self.ci_appels()   # le passage du conteneur : une fois, sans rejeu
        self.assertNotIn("--rejeu", ci)

    # --- passe Mac rouge (D9 : `run_all.sh <suites>` pour les suites Mac)
    def test_mac_rouge_puis_vert_au_rejeu_donne_71_par_le_runner_et_non_par_le_conteneur(self):
        avant = self.t.instantane()
        r = self.lancer_mac(["feat/a", "feat/b"], "suite_a", 0)
        self.code(r, 71, "runner non concluant : suites rouges non reproduites (suite_a) ; rien n'est fusionné")
        self.absent(r, "train rouge : suites en échec", LIGNE_70)
        complet, rejeu = self.t.appels("runner-neuf")
        self.assertIn("args=[suite_a]", rejeu)
        self.assertEqual(len(self.ci_appels()), 1, "le conteneur n'est lancé qu'une fois : le rejeu Mac ne passe pas par lui")
        self.rien_ne_change(avant)

    def test_mac_tout_autre_code_du_rejeu_donne_70(self):
        # côté Mac, tout code non nul du rejeu donne 70 (le 71 exigeant « rejeu rouge » ne vaut que pour le conteneur)
        for code in (2, 3):
            with self.subTest(code=code):
                r = self.lancer_mac(["feat/a"], "suite_a", code)
                self.code(r, 70, "train rouge : suites en échec : suite_a ; rien n'est fusionné")

    def test_mac_rouge_au_rejeu_donne_70(self):
        avant = self.t.instantane()
        r = self.lancer_mac(["feat/a"], "suite_a", 1)
        self.code(r, 70, "train rouge : suites en échec : suite_a ; rien n'est fusionné")
        self.assertEqual(len(self.t.appels("runner-neuf")), 2, "un seul rejeu")
        self.assertEqual(self.rejeus_ci(), [])
        self.rien_ne_change(avant)

    # --- groupe 3.6 : les trois cas de R-20261031-41
    def test_cas_1_l_indice_nomme_la_seule_branche_qui_a_selectionne_la_suite_rouge(self):
        avant = self.t.instantane()
        r = self.lancer(["feat/a", "feat/b", "feat/c"], "suite_b", 1)
        self.assertEqual(r.code, 70, r.texte)
        self.contient(r, f"{HINT_PREFIX} : feat/b\n", "finish_train : train rouge : suites en échec : suite_b ; rien n'est fusionné", LIGNE_70)
        self.absent(r, f"{HINT_PREFIX} : feat/a", f"{HINT_PREFIX} : feat/b, ", "par aucune branche", DEFAUT)
        self.assertEqual(len(self.ci_appels()), 2, "ni relance du train ni nouveau passage complet")
        self.rien_ne_change(avant)
        self.assertLess(r.texte.index(HINT_PREFIX), r.texte.index("train rouge : suites en échec"))

    def test_cas_2_l_indice_nomme_toutes_les_branches(self):
        avant = self.t.instantane()
        r = self.lancer(["feat/a", "feat/b", "feat/c"], "secret_scan", 1)   # une garde toujours sélectionnée : chaque branche la tient
        self.assertEqual(r.code, 70, r.texte)
        self.contient(r, f"{HINT_PREFIX} : feat/a, feat/b, feat/c", LIGNE_70)
        self.absent(r, DEFAUT)
        self.assertEqual(len(self.ci_appels()), 2, "aucune relance")
        self.rien_ne_change(avant)

    def test_cas_3_aucune_branche_ne_l_a_selectionnee_ligne_de_defaut_avant_la_banniere(self):
        avant = self.t.instantane()
        r = self.lancer(["feat/a", "feat/b"], "suite_z", 1)
        self.assertEqual(r.code, 70, r.texte)
        self.contient(r, f"{HINT_PREFIX} aucune branche", "finish_train : train rouge : suites en échec : suite_z ; rien n'est fusionné",
                      f"{DEFAUT} (suite_z) ; corriger le sélecteur avant le train suivant")
        texte = r.texte
        self.assertLess(texte.index(LIGNE_70), texte.index(DEFAUT))
        self.assertLess(texte.index(DEFAUT), texte.index(BANNIERE))
        self.assertEqual(len(self.ci_appels()), 2, "aucune relance")
        self.rien_ne_change(avant)

    def test_la_ligne_de_defaut_est_absente_apres_un_rejeu_vert(self):
        r = self.lancer(["feat/a"], "suite_z", 0)
        self.assertEqual(r.code, 71, r.texte)
        self.absent(r, DEFAUT)

    def test_selecteur_en_echec_indice_impossible_et_meme_code(self):
        # une liste de suites shell mal formée dans main fait échouer le sélecteur (code 2) pour chaque branche
        self.t.commit_main({"tests/suites_shell.txt": "ligne mal formée\n"}, "liste cassée", pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/d", {"tools/outil_d.sh": "d\n"})
        r = self.lancer(["feat/d"], "suite_b", 1)
        self.assertEqual(r.code, 70, r.texte)
        self.contient(r, "finish_train : indice impossible pour feat/d", "finish_train : train rouge : suites en échec : suite_b ; rien n'est fusionné", LIGNE_70)
        self.absent(r, DEFAUT)   # un sélecteur en échec n'est pas un défaut de sélection prouvé

    # --- corrections de la revue du 2026-10-31 (tests neufs, aucun test existant modifié)
    def test_selecteur_en_3_nomme_la_branche_et_ecarte_la_ligne_de_defaut(self):
        # une branche dont le sélecteur exige l'exécution complète (code 3) est comptée comme ayant tout sélectionné (D5) : nommée dans l'indice,
        # et la suite rouge hors de toute autre sélection n'est donc pas un défaut de sélection
        self.t.branche("feat/o", {"tools/orphelin.py": "pass\n"})
        r = self.lancer(["feat/a", "feat/o"], "suite_z", 1)
        self.assertEqual(r.code, 70, r.texte)
        self.contient(r, f"{HINT_PREFIX} : feat/o\n", LIGNE_70)
        self.absent(r, f"{HINT_PREFIX} : feat/a", "par aucune branche", DEFAUT)

    def test_le_rejeu_n_ecrit_aucune_empreinte_et_ne_recoit_que_les_noms(self):
        # les faux notent dans ecrit.log toute option autre que --rejeu (--branch, --staged, --mac... qui feraient écrire une empreinte, un verdict
        # ou une preuve) : le rejeu du conteneur n'en passe aucune ; il ne reçoit que --rejeu et les noms
        r = self.lancer(["feat/a"], "suite_a", 0, FAKE_RUNNER_ECRIVAIN="1")
        self.assertEqual(r.code, 71, r.texte)
        (rejeu,) = self.rejeus_ci()
        self.assertEqual(self.noms_du_rejeu(rejeu), ["suite_a"])
        self.assertFalse((self.t.etat / "ecrit.log").exists(), "le rejeu a écrit une empreinte")

    def test_le_rejeu_mac_n_ecrit_aucune_empreinte_et_ne_recoit_que_les_noms(self):
        r = self.lancer_mac(["feat/a"], "suite_a", 0, FAKE_RUNNER_ECRIVAIN="1")
        self.assertEqual(r.code, 71, r.texte)
        (_, rejeu) = self.t.appels("runner-neuf")
        self.assertIn("args=[suite_a]", rejeu)
        self.assertFalse((self.t.etat / "ecrit.log").exists(), "le rejeu Mac a écrit une empreinte")

    def test_un_nom_suspect_est_refuse_en_71_avant_tout_rejeu_et_rien_n_est_execute(self):
        # réécrit (test de sécurité, R-20261101-115 ; revue Opus point 3) : le code est plus strict qu'avant. Un nom de suite qui porte un méta-caractère du
        # shell (« ; ») est refusé en 71 AVANT tout rejeu (jamais passé au conteneur) ; la commande injectée (ici la création d'un fichier marqueur) n'a
        # jamais été exécutée. Le passage complet a tourné une fois, aucun rejeu, rien n'est fusionné.
        marqueur = self.t.etat / "marqueur-injection"
        nom = f"suite_a;touch {marqueur}"
        avant = self.t.instantane()
        r = self.lancer(["feat/a"], nom, 1)
        self.code(r, 71, "runner non concluant : nom de suite refusé pour le rejeu ; rien n'est fusionné")
        self.assertEqual(self.rejeus_ci(), [], "aucun rejeu n'est lancé pour un nom suspect")
        self.assertEqual(len(self.ci_appels()), 1, "seul le passage complet a tourné")
        self.assertFalse(marqueur.exists(), "la commande injectée a été exécutée")
        self.assertEqual(self.t.appels("runner-neuf"), [], "la passe Mac n'est pas lancée")
        self.rien_ne_change(avant)

    def un_nom_hors_du_motif_n_est_pas_rejoue(self, nom):
        # Q230 (R-20261101-118), côté finish_train.sh : un nom de suite hors de [A-Za-z0-9_]+ dans une ligne rouge portable n'est jamais rejoué
        # (aucun appel --rejeu dans ci-appels) ; même motif que dans ci_local.sh, dont le test est de l'autre côté (tests/ci_local)
        avant = self.t.instantane()
        r = self.lancer(["feat/a"], nom, 1)
        self.code(r, 71, "runner non concluant : nom de suite refusé pour le rejeu ; rien n'est fusionné")
        self.assertEqual(self.rejeus_ci(), [], f"le nom {nom!r} a été rejoué")
        self.assertEqual(len(self.ci_appels()), 1, "seul le passage complet a tourné")
        self.assertEqual(self.t.appels("runner-neuf"), [], "la passe Mac n'est pas lancée")
        self.rien_ne_change(avant)

    def test_un_nom_avec_un_tiret_n_est_pas_rejoue(self):
        self.un_nom_hors_du_motif_n_est_pas_rejoue("suite-a")

    def test_un_nom_avec_un_point_n_est_pas_rejoue(self):
        self.un_nom_hors_du_motif_n_est_pas_rejoue("suite.a")

    def test_un_nom_avec_une_barre_n_est_pas_rejoue(self):
        self.un_nom_hors_du_motif_n_est_pas_rejoue("../suite_a")

    def test_les_noms_valides_du_rejeu_passent_en_arguments(self):
        # le rejeu du conteneur reçoit les noms valides tels quels, un argument chacun, après --rejeu
        self.lancer(["feat/a"], "suite_a suite_b", 1)
        (rejeu,) = self.rejeus_ci()
        self.assertEqual(self.noms_du_rejeu(rejeu), ["suite_a", "suite_b"])

    def test_un_nom_suspect_du_rejeu_mac_est_refuse_en_71_sans_rejeu(self):
        # R-20261101-120 (Q236 a), plus strict qu'avant (le nom suspect était passé tel quel en argument) : le même refus que côté conteneur, avant tout rejeu
        marqueur = self.t.etat / "marqueur-injection-mac"
        avant = self.t.instantane()
        r = self.lancer_mac(["feat/a"], f"suite_a;touch {marqueur}", 1)
        self.code(r, 71, "runner non concluant : nom de suite refusé pour le rejeu ; rien n'est fusionné")
        self.assertEqual(len(self.t.appels("runner-neuf")), 1, "seule la passe Mac complète a tourné : aucun rejeu au runner")
        self.assertFalse(marqueur.exists(), "la commande injectée a été exécutée")
        self.rien_ne_change(avant)

    def test_les_noms_valides_du_rejeu_mac_passent_en_arguments_un_chacun(self):
        self.lancer_mac(["feat/a"], "suite_a suite_b", 1)
        (_, rejeu) = self.t.appels("runner-neuf")
        self.assertIn("args=[suite_a suite_b]", rejeu)   # le faux note $* : les deux noms arrivent comme arguments séparés

    def test_la_ligne_total_du_rejeu_entre_au_journal(self):
        r = self.lancer(["feat/a"], "suite_a", 1)
        self.assertEqual(r.code, 70, r.texte)
        self.assertEqual(r.texte.count("TOTAL : 1 tests dans 1 suites · tous réussis"), 1, r.texte)
        # le train ne réimprime du passage complet que les lignes « ci_passage : » et « ci_local : » (pas son TOTAL) ; il réimprime la ligne TOTAL du rejeu,
        # après la ligne de phase rouge du passage complet
        self.assertNotIn("TOTAL : 3 tests dans 2 suites", r.texte)
        self.assertLess(r.texte.index("ci_passage : phase portable : rouge · 3 s : suite_a"), r.texte.index("TOTAL : 1 tests dans 1 suites"))


if __name__ == "__main__":
    unittest.main()
