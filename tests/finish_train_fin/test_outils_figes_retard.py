"""
Niveau 2 du bac à sable de Bash, décision R-20261110-03 : le rafraîchissement des copies figées (étape « outils figés » de tools/finish_train.sh) exige le « o » de
l'auteur. Dans son train, la question o/n suit la question d'arrivée ; après « n », ou en mode automatique (--auto), le train fusionne sans rien copier et note le
retard (« copies figées en retard sur main », la commande exacte de rafraîchissement) dans le fichier outils-figes-en-retard du dossier de données, que le rapport des
fusions automatiques lit. Un rafraîchissement réussi retire la note.
Dépôts jetables de l'aide commune (aide_train) ; mêmes dépôts que la suite des outils figés. Remplace : rien. Retrait : avec le bac à sable.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, OUTILS  # noqa: E402

sys.path.insert(0, str(OUTILS))
import train_ready  # noqa: E402
import train_record  # noqa: E402

LISTE = "E ci_local.sh\nC tools/dependance.py\n"
QUESTION = "Rafraîchir les copies figées du bac à sable ? (o/n)"
RETARD = "copies figées en retard sur main"
PHRASE = "finish_train : outils figés rafraîchis"


class AvecJournal(AvecTrain):
    """Le strict nécessaire de l'aide du même nom de la suite du journal des trains (copié ici : aucun couplage entre suites)."""
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.t.data)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def journal(self):
        chemin = self.t.data / "trains" / "journal.jsonl"
        return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines()] if chemin.exists() else []


class RetardDesCopiesFigees(AvecJournal):
    def setUp(self):
        super().setUp()
        self.t.sans_substitution = True   # R-20261106-57 : sous --auto, les faux sont dans l'arbre d'exécution
        copie = (OUTILS / "outils_figes" / "rafraichir.sh").read_text(encoding="utf-8")
        self.t.commit_main({"tools/outils_figes/liste.txt": LISTE, "tools/outils_figes/rafraichir.sh": copie,
                            "tools/outils_figes/ci_local.sh": "enveloppe v1\n", "tools/dependance.py": "dependance v1\n"},
                           "outils figés", pousser=True)
        self.t.mettre_a_jour_run()
        self.dest = self.t.data / "outils-figes"
        self.dest.mkdir(parents=True)
        (self.dest / "dossiers.conf").write_text("maison=/m\n", encoding="utf-8")
        self.marqueur = self.t.data / "outils-figes-en-retard"
        self.t.branche("feat/x", {"tools/dependance.py": "dependance v2\n"})

    def liste_prete(self, nom):
        """La liste prête de la branche et une activation valide (cinq trains verts au journal), comme la suite de --auto."""
        dossier = self.t.data / "train-auto"
        dossier.mkdir(parents=True, exist_ok=True)
        train_ready.write_list([{"branche": nom, "sommet": self.t.sommet(nom), "empreinte": "e" * 40, "revue": "faite", "ajout": "2026-11-06T09:00:00Z"}])
        for c in "12345":
            train_record.append({"heure": "2026-11-06T10:00:00Z", "code": 0, "sens": "fusionne", "mode": "manuel", "n": 2, "sommets": ["a" * 40],
                                 "sommet_train": c * 40, "main_avant": "9" * 40, "main_apres": c * 40, "runner": "conteneur", "base": False,
                                 "front": True, "politique": [], "duree_s": 600, "etape": ""})
        fichier = dossier / "fusion-active"
        fichier.write_text(json.dumps({"format": 1, "heure": "2026-11-06T12:00:00Z", "serie": [c * 40 for c in "12345"]}), encoding="utf-8")
        os.chmod(fichier, 0o600)

    def inchange(self):
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])   # aucune copie touchée
        self.assertEqual(sorted(p.name for p in self.dest.parent.glob("outils-figes.*")), [])

    def test_en_auto_le_train_fusionne_sans_rafraichir_et_note_le_retard(self):
        self.liste_prete("feat/x")
        r = self.t.lance("--auto", "feat/x")
        self.code(r, 0, "main poussé vers origin", RETARD, "Pour les rafraîchir : cd ")
        self.contient(r, "tools/outils_figes/rafraichir.sh")   # au milieu de la ligne « Pour les rafraîchir : cd ... »
        self.absent(r, QUESTION, PHRASE)
        self.inchange()
        self.assertEqual(self.t.main(), self.t.origin_main())
        sommet, _, commande = self.marqueur.read_text(encoding="utf-8").strip().partition(" ")
        self.assertEqual(sommet, self.journal()[-1]["sommet_train"])   # le retard est celui de CE train : le rapport le relie à son enregistrement
        self.assertIn("bash tools/outils_figes/rafraichir.sh", commande)
        self.assertIn(str(self.dest), commande)
        self.assertNotIn("--extrait-du-train", commande)               # R-20261110-07 : la commande de l'auteur reste à deux arguments

    def test_en_auto_une_reponse_o_sur_l_entree_ne_change_rien(self):
        self.liste_prete("feat/x")
        r = self.t.lance("--auto", "feat/x", entree="o\no\n")
        self.code(r, 0, RETARD)
        self.absent(r, QUESTION, PHRASE)
        self.inchange()

    def test_apres_n_aucune_copie_et_le_retard_est_note(self):
        r = self.t.lance("feat/x", entree="o\nn\n")
        self.code(r, 0, "main poussé vers origin", RETARD, "Pour les rafraîchir : cd ")
        self.contient(r, QUESTION)
        self.absent(r, PHRASE)
        self.inchange()
        self.assertTrue(self.marqueur.read_text(encoding="utf-8").startswith(self.t.main()))

    def test_sans_reponse_le_rafraichissement_n_a_pas_lieu(self):
        r = self.t.lance("feat/x", entree="o\n")   # entrée fermée à la seconde question : jamais un « o »
        self.code(r, 0, RETARD)
        self.absent(r, PHRASE)
        self.inchange()
        self.assertTrue(self.marqueur.exists())
        self.assertTrue(self.marqueur.read_text(encoding="utf-8").startswith(self.t.main()))

    def test_une_reponse_autre_que_o_ne_rafraichit_pas_et_note_le_retard(self):
        # question() lit une ligne et la compare à « o » seulement : « oui » ne vaut pas « o ».
        r = self.t.lance("feat/x", entree="o\noui\n")
        self.code(r, 0, RETARD)
        self.absent(r, PHRASE)
        self.inchange()
        self.assertTrue(self.marqueur.read_text(encoding="utf-8").startswith(self.t.main()))

    def test_une_majuscule_ne_rafraichit_pas_et_note_le_retard(self):
        r = self.t.lance("feat/x", entree="o\nO\n")
        self.code(r, 0, RETARD)
        self.absent(r, PHRASE)
        self.inchange()
        self.assertTrue(self.marqueur.exists())

    def test_la_note_est_ecrite_sans_fichier_temporaire_laisse(self):
        r = self.t.lance("feat/x", entree="o\nn\n")
        self.code(r, 0, RETARD)
        self.assertEqual(sorted(p.name for p in self.t.data.glob("outils-figes-en-retard*")), ["outils-figes-en-retard"])

    def test_un_lien_pose_a_la_place_de_la_note_n_est_pas_suivi(self):
        cible = self.t.data / "cible-du-lien"
        cible.write_text("intact\n", encoding="utf-8")
        self.marqueur.symlink_to(cible)
        r = self.t.lance("feat/x", entree="o\nn\n")
        self.code(r, 0, RETARD)
        self.assertEqual(cible.read_text(encoding="utf-8"), "intact\n")
        self.assertFalse(self.marqueur.is_symlink())
        self.assertTrue(self.marqueur.read_text(encoding="utf-8").startswith(self.t.main()))

    def test_un_echec_apres_o_ecrit_la_note_sans_changer_le_code_de_l_echec(self):
        (self.dest / "dossiers.conf").unlink()   # sans dossiers.conf, le script de copie rend 4
        r = self.t.lance("feat/x", entree="o\no\n")
        self.assertEqual(r.code, 75, r.texte)
        self.contient(r, "outils figés non rafraîchis (code 4)", RETARD)
        self.assertTrue(self.marqueur.read_text(encoding="utf-8").startswith(self.t.main()))

    def test_un_echec_apres_o_remplace_une_note_existante_par_celle_du_train(self):
        self.marqueur.write_text("0" * 40 + " cd /ailleurs && bash tools/outils_figes/rafraichir.sh /ailleurs /copies\n", encoding="utf-8")
        (self.dest / "dossiers.conf").unlink()
        r = self.t.lance("feat/x", entree="o\no\n")
        self.assertEqual(r.code, 75, r.texte)
        texte = self.marqueur.read_text(encoding="utf-8")
        self.assertTrue(texte.startswith(self.t.main()), texte)
        self.assertNotIn("/ailleurs", texte)

    def test_apres_o_les_copies_sont_rafraichies_et_un_ancien_retard_est_retire(self):
        self.marqueur.write_text("0" * 40 + " cd /ailleurs && bash tools/outils_figes/rafraichir.sh /ailleurs /copies\n", encoding="utf-8")
        r = self.t.lance("feat/x", entree="o\no\n")
        self.code(r, 0)
        self.contient(r, QUESTION, PHRASE)   # la question est affichée par question() sans le préfixe ; PHRASE porte déjà le sien
        self.absent(r, RETARD)
        self.assertEqual((self.dest / "copie" / "tools" / "dependance.py").read_text(encoding="utf-8"), "dependance v2\n")
        self.assertFalse(self.marqueur.exists())

    def test_un_train_sans_fichier_figé_ne_pose_pas_la_question(self):
        self.t.branche("feat/y", {"tools/sans_rapport.sh": "x\n"})
        r = self.t.lance("feat/y", entree="o\n")
        self.code(r, 0)
        self.absent(r, QUESTION, RETARD, "outils figés")
        self.assertFalse(self.marqueur.exists())

    def test_lecture_du_script_la_question_precede_la_preparation(self):
        texte = (OUTILS / "finish_train.sh").read_text(encoding="utf-8")
        corps = texte[texte.index("frozen_prepare() {"):]
        corps = corps[:corps.index("\n}\n")]
        self.assertLess(corps.index("frozen_ask"), corps.index('FROZEN_PREP="$dest.preparation.$$"'))
        self.assertLess(corps.index('if [ "$AUTO" = 1 ]'), corps.index('FROZEN_PREP="$dest.preparation.$$"'))


if __name__ == "__main__":
    unittest.main()
