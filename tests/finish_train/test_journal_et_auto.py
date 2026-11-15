"""
Le journal des trains de tools/finish_train.sh (autonomous-trains-merge, tâche 3.2, design D4).

    bash tests/run_all.sh finish_train

  - journal : une ligne par lancement qui a pris le verrou de fin et qui n'est pas un essai rapide, écrite par tools/train_record.py dans le piège de sortie,
    avant la libération du verrou ; `code` et `sens` égaux à la bannière ; `runner` `remplace` sous FINISH_TRAIN_CI ou FINISH_TRAIN_RUNNER ; aucun nom ;
    une écriture impossible ne change aucun refus et devient une cause du code 75 après une fusion.

Dépôts jetables de l'aide commune (aide_train) ; les faux (runner, conteneur, garde du matin) sont ceux des autres suites du train.
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_train import AvecTrain, CHEMIN_INTERFACE  # noqa: E402

BANNIERE = re.compile(r"^===== fin du train : code (\d+) \((fusionné|essai|refusé|interrompu)\), .* Paris =====$", re.M)
SENS_ASCII = {"fusionné": "fusionne", "essai": "essai", "refusé": "refuse", "interrompu": "interrompu"}
SANS_SUBSTITUTION = {"FINISH_TRAIN_RUNNER": None, "FINISH_TRAIN_CI": None}


class AvecJournal(AvecTrain):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.t.data)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def journal(self):
        chemin = self.t.data / "trains" / "journal.jsonl"
        return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines()] if chemin.exists() else []

    def banniere(self, r):
        m = BANNIERE.search(r.texte)
        self.assertIsNotNone(m, r.texte)
        return int(m.group(1)), m.group(2)


class Journal(AvecJournal):
    def test_fusion_de_l_auteur_ecrit_une_ligne_sans_nom(self):
        self.t.branche("feat/x")
        tip, avant = self.t.sommet("feat/x"), self.t.main()
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 0)
        (rec,) = self.journal()
        self.assertEqual((rec["format"], rec["mode"], rec["code"], rec["sens"], rec["n"]), (1, "manuel", 0, "fusionne", 1))
        self.assertEqual(rec["sommets"], [tip])
        self.assertEqual((rec["main_avant"], rec["main_apres"]), (avant, self.t.main()))
        self.assertEqual(rec["sommet_train"], self.t.main())
        self.assertEqual((rec["etape"], rec["politique"]), ("", []))
        self.assertEqual(rec["runner"], "remplace")   # les faux du dépôt jetable posent FINISH_TRAIN_CI et FINISH_TRAIN_RUNNER
        texte = (self.t.data / "trains" / "journal.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("feat", texte)
        self.assertNotIn("feat/x", texte)

    def test_le_journal_est_ecrit_avant_la_banniere_et_le_verrou_est_libere_apres(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 0)
        self.assertEqual(len(self.journal()), 1)
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists())
        self.assertRegex(self.t.log().splitlines()[-1], BANNIERE.pattern)

    def test_essai_rapide_n_ecrit_rien(self):
        self.t.branche("feat/x")
        r = self.t.lance("--essai", "feat/x")
        self.code(r, 0)
        self.assertEqual(self.journal(), [])
        self.assertFalse((self.t.data / "trains").exists())

    def test_reponse_n_est_un_enregistrement_de_sens_essai(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="n\n")
        self.code(r, 0)
        (rec,) = self.journal()
        self.assertEqual((rec["code"], rec["sens"], rec["mode"]), (0, "essai", "manuel"))

    def test_refus_enregistre_avec_l_etape(self):
        r = self.t.lance("feat/inconnue")
        self.code(r, 62)
        (rec,) = self.journal()
        self.assertEqual((rec["code"], rec["sens"], rec["etape"], rec["sommets"]), (62, "refuse", "admission", []))

    def test_runner_conteneur_sans_variable_de_substitution(self):
        r = self.t.lance("feat/inconnue", extra=SANS_SUBSTITUTION)
        self.code(r, 62)
        self.assertEqual(self.journal()[0]["runner"], "conteneur")

    def test_runner_remplace_sous_l_une_ou_l_autre_variable(self):
        for retiree in ("FINISH_TRAIN_RUNNER", "FINISH_TRAIN_CI"):
            with self.subTest(retiree=retiree):
                (self.t.data / "trains" / "journal.jsonl").unlink(missing_ok=True)
                for f in self.t.journaux():
                    f.unlink()
                r = self.t.lance("feat/inconnue", extra={retiree: None})
                self.code(r, 62)
                self.assertEqual(self.journal()[0]["runner"], "remplace")

    def test_le_code_et_le_sens_sont_ceux_de_la_banniere(self):
        self.t.branche("feat/x")
        self.t.branche("feat/y")
        scenarios = [
            (("feat/x",), {}, "o\n"),                                                        # 0 fusionné
            (("feat/y",), {}, "n\n"),                                                        # 0 essai
            (("feat/inconnue",), {}, ""),                                                    # 62 refusé
            (("feat/y",), {"FAUX_CI_CODE": "3", "FAUX_CI_LIGNES": "ci_local : conteneur indisponible"}, "o\n"),   # 71 refusé
        ]
        for branches, extra, entree in scenarios:
            with self.subTest(branches=branches, extra=extra):
                for f in self.t.journaux():
                    f.unlink()
                r = self.t.lance(*branches, extra=extra, entree=entree)
                code, sens = self.banniere(r)
                self.assertEqual(r.code, code)
                rec = self.journal()[-1]
                self.assertEqual((rec["code"], rec["sens"]), (code, SENS_ASCII[sens]))
        self.assertEqual([r["code"] for r in self.journal()], [0, 0, 62, 71])

    def test_base_et_front_viennent_des_controles_14_et_16_de_l_arbre(self):
        self.t.branche("feat/db", {"db/001.sql": "SELECT 2;\n"})
        r = self.t.lance("feat/db", entree="o\n")
        self.code(r, 0)
        (rec,) = self.journal()
        self.assertEqual((rec["base"], rec["front"]), (True, False))
        self.t.branche("feat/ui", {CHEMIN_INTERFACE: "x\n"})
        for f in self.t.journaux():
            f.unlink()
        r = self.t.lance("feat/ui", entree="o\n")
        self.code(r, 0)
        self.assertEqual((self.journal()[-1]["base"], self.journal()[-1]["front"]), (False, True))

    def test_verrou_tenu_par_un_autre_n_ecrit_rien(self):
        self.t.branche("feat/x")
        self.t.verrou_etranger()
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 67)
        self.assertEqual(self.journal(), [])

    def test_refus_de_lancement_avant_le_verrou_n_ecrit_rien(self):
        self.t.branche("feat/x")
        r = self.t.lance("--inconnue", "feat/x")
        self.code(r, 60)
        self.assertEqual(self.journal(), [])

    def test_les_enregistrements_de_plus_d_un_an_sont_retires(self):
        dossier = self.t.data / "trains"
        dossier.mkdir(parents=True)
        vieux = {"format": 1, "heure": "2024-01-01T10:00:00Z", "code": 0, "sens": "fusionne", "mode": "manuel", "n": 1, "sommets": [], "sommet_train": "",
                 "main_avant": "", "main_apres": "", "runner": "conteneur", "base": False, "front": False, "politique": [], "duree_s": 1, "etape": ""}
        (dossier / "journal.jsonl").write_text(json.dumps(vieux) + "\n", encoding="utf-8")
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="n\n")
        self.code(r, 0)
        self.assertEqual([x["heure"] for x in self.journal() if x["heure"].startswith("2024")], [])
        self.assertEqual(len(self.journal()), 1)


class JournalNonEcrit(AvecJournal):
    PHRASE = "journal des trains non écrit (écriture impossible)"

    def rendre_non_inscriptible(self):
        """Un fichier à la place du dossier du journal : l'écriture est impossible sans toucher au reste."""
        self.t.data.mkdir(parents=True, exist_ok=True)
        (self.t.data / "trains").write_text("pas un dossier", encoding="utf-8")

    def test_apres_une_fusion_c_est_une_cause_du_code_75(self):
        self.rendre_non_inscriptible()
        self.t.branche("feat/x")
        avant = self.t.main()
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 75, self.PHRASE, "train fusionné et poussé, fin incomplète :")
        self.contient(r, "  - " + self.PHRASE)
        self.assertNotEqual(self.t.main(), avant)
        self.assertEqual(self.t.main(), self.t.origin_main())
        self.assertEqual(self.t.distant_main(), self.t.main())
        code, sens = self.banniere(r)
        self.assertEqual((code, sens), (75, "fusionné"))
        self.assertIn("===== arrêt à journal des trains :", r.texte)
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists(), "le verrou est libéré")

    def test_apres_un_refus_le_code_ne_change_pas(self):
        self.rendre_non_inscriptible()
        r = self.t.lance("feat/inconnue")
        self.code(r, 62, self.PHRASE)
        self.assertEqual(self.banniere(r), (62, "refusé"))

    def test_apres_la_reponse_n_le_code_reste_0(self):
        self.rendre_non_inscriptible()
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="n\n")
        self.code(r, 0, self.PHRASE)
        self.assertEqual(self.banniere(r), (0, "essai"))


if __name__ == "__main__":
    unittest.main()
