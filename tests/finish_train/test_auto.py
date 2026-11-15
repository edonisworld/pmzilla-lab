"""
L'option --auto de tools/finish_train.sh (autonomous-trains-merge, tâche 3.6, design D7, D8, D19).

    bash tests/run_all.sh finish_train

  - 60 avec --essai, 61 depuis un terminal (aucune variable ne l'accepte), 61 avec FINISH_TRAIN_CI ou FINISH_TRAIN_RUNNER posée (R-20261106-57), 84 en reprise S1 ou S2 (rien n'est poussé) ;
  - la politique au point de la question : autorisée, l'arrivée suit comme après « o » ; refusée, une ligne par raison et 84, rien n'est fusionné ;
  - le calcul impossible de la politique donne 84 et « contrôles de fin impossibles ».

Dépôts jetables de l'aide commune (aide_train) ; la liste prête, l'arrêt et l'activation sont écrits par les modules qui les lisent.
"""
import json
import os
import pty
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_train import BASH, OUTILS, RUN_ALL_BIDON  # noqa: E402
from test_journal_et_auto import AvecJournal  # noqa: E402

sys.path.insert(0, str(OUTILS))
import train_ready  # noqa: E402
import train_record  # noqa: E402


class Auto(AvecJournal):
    def setUp(self):
        super().setUp()
        self.t.sans_substitution = True   # R-20261106-57 : aucune exception à la garde pour les tests ; les faux sont dans l'arbre d'exécution

    def preparer(self, *noms, revue="faite", activer=True):
        """Des branches de code, la liste prête (`revue`) et, par défaut, une activation valide (cinq trains verts au journal)."""
        tips = [self.t.sommet(n) for n in noms]
        dossier = self.t.data / "train-auto"
        dossier.mkdir(parents=True, exist_ok=True)
        train_ready.write_list([{"branche": n, "sommet": s, "empreinte": "e" * 40, "revue": revue, "ajout": "2026-11-06T09:00:00Z"} for n, s in zip(noms, tips)])
        if activer:
            for c in "12345":
                train_record.append({"heure": "2026-11-06T10:00:00Z", "code": 0, "sens": "fusionne", "mode": "manuel", "n": 2, "sommets": ["a" * 40],
                                     "sommet_train": c * 40, "main_avant": "9" * 40, "main_apres": c * 40, "runner": "conteneur", "base": False,
                                     "front": True, "politique": [], "duree_s": 600, "etape": ""})
            fichier = dossier / "fusion-active"
            fichier.write_text(json.dumps({"format": 1, "heure": "2026-11-06T12:00:00Z", "serie": [c * 40 for c in "12345"]}), encoding="utf-8")
            os.chmod(fichier, 0o600)
        return tips

    def depuis_un_terminal(self, env):
        """Lance `--auto feat/a` avec l'entrée standard sur un terminal (pty) ; rend le résultat du processus."""
        maitre, esclave = pty.openpty()
        try:
            return subprocess.run([BASH, str(self.t.script()), "--auto", "feat/a"], cwd=self.t.lab, env=env, stdin=esclave,
                                  capture_output=True, text=True, timeout=120)
        finally:
            os.close(maitre)
            os.close(esclave)

    def test_auto_et_essai_ne_vont_pas_ensemble(self):
        self.t.branche("feat/a")
        avant = self.t.instantane()
        r = self.t.lance("--auto", "--essai", "feat/a")
        self.code(r, 60, "usage : --auto et --essai ne vont pas ensemble")
        self.rien_ne_change(avant)
        self.assertEqual(self.journal(), [])

    def test_auto_donne_deux_fois_est_un_usage_errone(self):
        self.t.branche("feat/a")
        r = self.t.lance("--auto", "--auto", "feat/a")
        self.assertEqual(r.code, 60, r.texte)

    def test_depuis_un_terminal_61(self):
        self.t.branche("feat/a")
        avant = self.t.instantane()
        fait = self.depuis_un_terminal(self.t.env())
        self.assertEqual(fait.returncode, 61, fait.stdout + fait.stderr)
        self.assertIn("finish_train : lancement refusé : --auto depuis un terminal ; le train de l'auteur garde la question", fait.stdout)
        self.rien_ne_change(avant)
        self.assertEqual(self.journal(), [])

    def test_aucune_variable_n_accepte_auto_depuis_un_terminal(self):
        self.t.branche("feat/a")
        fait = self.depuis_un_terminal(self.t.env(extra={"FINISH_TRAIN_AUTO": "1", "AUTO_OK": "1", "FINISH_TRAIN_ALLOW_TTY": "1", "TRAIN_AUTO_NOW": "1"}))
        self.assertEqual(fait.returncode, 61, fait.stdout + fait.stderr)

    def refus_variable(self, extra):
        self.t.branche("feat/a")
        self.preparer("feat/a")
        avant, distant = self.t.main(), self.t.origin_main()
        r = self.t.lance("--auto", "feat/a", extra=extra)
        self.code(r, 61, "lancement refusé : --auto avec FINISH_TRAIN_CI ou FINISH_TRAIN_RUNNER posée")
        self.absent(r, "mode automatique : la politique remplace la question", "départ autorisé")
        self.assertEqual((self.t.main(), self.t.origin_main()), (avant, distant))   # rien n'est fusionné, rien n'est poussé

    def test_auto_avec_finish_train_ci_61(self):
        self.refus_variable({"FINISH_TRAIN_CI": f"bash {self.t.ci}"})

    def test_auto_avec_finish_train_runner_61(self):
        self.refus_variable({"FINISH_TRAIN_RUNNER": f"bash {self.t.runner}"})

    def test_auto_avec_les_deux_variables_61(self):
        self.refus_variable({"FINISH_TRAIN_CI": f"bash {self.t.ci}", "FINISH_TRAIN_RUNNER": f"bash {self.t.runner}"})

    def test_politique_autorise_le_train_comme_apres_o(self):
        self.t.branche("feat/a")
        self.t.branche("feat/b")
        self.preparer("feat/a", "feat/b")
        avant = self.t.main()
        r = self.t.lance("--auto", "feat/a", "feat/b")
        self.code(r, 0, "mode automatique : la politique remplace la question", "politique automatique : départ autorisé (2 branche(s))",
                  "main poussé vers origin")
        self.absent(r, "Terminer le train", "politique automatique refuse")
        self.assertNotEqual(self.t.main(), avant)
        self.assertEqual(self.t.main(), self.t.origin_main())
        recs = self.journal()
        self.assertEqual((recs[-1]["mode"], recs[-1]["code"], recs[-1]["sens"], recs[-1]["politique"]), ("auto", 0, "fusionne", []))

    def test_auto_ne_lit_pas_l_entree_standard(self):
        self.t.branche("feat/a")
        self.preparer("feat/a")
        r = self.t.lance("--auto", "feat/a", entree="n\n")   # un « n » sur l'entrée ne change rien : la question n'est pas posée
        self.code(r, 0, "politique automatique : départ autorisé (1 branche(s))")

    def test_revue_absente_84(self):
        self.t.branche("feat/a")
        self.preparer("feat/a", revue="non-requise")
        avant_main = self.t.main()
        r = self.t.lance("--auto", "feat/a")
        self.code(r, 84, "mode automatique : la politique remplace la question",
                  "politique automatique refuse : revue Opus absente pour ce sommet (feat/a) ; rien n'est fusionné")
        self.assertEqual(self.t.main(), avant_main)
        self.assertEqual(self.t.origin_main(), avant_main)
        self.assertRegex(r.texte, r"===== fin du train : code 84 \(refusé\), \d{4}-\d\d-\d\d \d\d:\d\d:\d\d Paris =====")
        self.assertIn("===== arrêt à politique automatique : rien n'est fusionné =====", r.texte)
        (rec,) = self.journal()[-1:]
        self.assertEqual((rec["code"], rec["sens"], rec["mode"], rec["etape"], rec["politique"]), (84, "refuse", "auto", "politique automatique", ["revue-absente"]))

    def test_chaque_raison_a_sa_ligne_dans_l_ordre(self):
        self.t.branche("feat/a")
        self.preparer("feat/a", revue="non-requise", activer=False)
        (self.t.data / "train-auto" / "arret").write_text("", encoding="utf-8")
        r = self.t.lance("--auto", "feat/a")
        self.assertEqual(r.code, 84, r.texte)
        lignes = [l for l in r.texte.splitlines() if l.startswith("finish_train : politique automatique refuse")]
        self.assertEqual(lignes, ["finish_train : politique automatique refuse : fusion automatique non activée ; rien n'est fusionné",
                                  "finish_train : politique automatique refuse : arrêt d'urgence actif ; rien n'est fusionné",
                                  "finish_train : politique automatique refuse : revue Opus absente pour ce sommet (feat/a) ; rien n'est fusionné"])
        self.assertEqual(self.journal()[-1]["politique"], ["inactif", "arret", "revue-absente"])

    def test_sans_activation_c_est_le_mode_observation_84(self):
        self.t.branche("feat/a")
        self.preparer("feat/a", activer=False)
        r = self.t.lance("--auto", "feat/a")
        self.code(r, 84, "politique automatique refuse : fusion automatique non activée ; rien n'est fusionné")
        self.assertEqual(self.t.main(), self.t.origin_main())

    def test_une_branche_du_runner_meme_seule_84(self):
        self.t.branche("feat/run", {"tests/run_all.sh": RUN_ALL_BIDON + "# autre\n"})   # le runner du train est celui de l'arbre (aucune variable sous --auto) : il reste un runner vert
        self.preparer("feat/run")
        avant = self.t.main()
        r = self.t.lance("--auto", "feat/run")
        self.code(r, 84, "politique automatique refuse : outillage de fin, runner, preuve, .claude/, CLAUDE.md ou postures : train de l'auteur (feat/run) ; rien n'est fusionné")
        self.assertEqual(self.t.main(), avant)

    def test_calcul_impossible_84(self):
        self.t.branche("feat/a")
        self.preparer("feat/a")
        self.t.casser_le_module("train_auto.py", "raise RuntimeError('casse')\n")
        r = self.t.lance("--auto", "feat/a")
        self.code(r, 84, "politique automatique refuse : contrôles de fin impossibles ; rien n'est fusionné")
        self.assertEqual(self.journal()[-1]["politique"], ["calcul-impossible"])
        self.assertEqual(self.t.main(), self.t.origin_main())

    def test_etat_de_reprise_s1_84_sans_push(self):
        self.t.branche("feat/a")
        self.t.etat_fusionne_localement("feat/a")
        distant = self.t.distant_main()
        r = self.t.lance("--auto", "feat/a")
        self.code(r, 84, "politique automatique refuse : état de reprise (S1) ; train de l'auteur")
        self.assertEqual(self.t.distant_main(), distant)

    def test_etat_de_reprise_s2_84(self):
        self.t.branche("feat/a")
        self.t.sans_substitution = False   # la mise en état S2 est un train manuel (faux runner de l'aide) ; le lancement --auto qui suit n'a aucune variable
        self.t.etat_pousse("feat/a")
        self.t.sans_substitution = True
        r = self.t.lance("--auto", "feat/a")
        self.code(r, 84, "politique automatique refuse : état de reprise (S2) ; train de l'auteur")

    def test_aucune_branche_refusee_a_l_admission_n_arrive_au_point_de_la_question(self):
        r = self.t.lance("--auto", "feat/inconnue")
        self.code(r, 62)
        self.absent(r, "mode automatique : la politique remplace la question")


if __name__ == "__main__":
    unittest.main()
