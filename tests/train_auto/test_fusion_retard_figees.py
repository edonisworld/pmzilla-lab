"""
Décision R-20261110-03 : le rapport des fusions automatiques signale le retard des copies figées que le train a noté (fichier outils-figes-en-retard du dossier de
données : le sommet du train, un espace, la commande exacte de rafraîchissement). Le signalement ne vient que du train du passage, jamais d'un retard plus ancien ;
sans note, la ligne du rapport est celle d'avant. Remplace : rien. Retrait : avec le bac à sable.

    bash tests/run_all.sh train_auto
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402

COMMANDE = 'cd "/espace" && bash tools/outils_figes/rafraichir.sh "/espace" "/donnees/outils-figes"'
SOMMET = "c" * 40


def rapport():
    return {"heure": "2026-11-10 12:05", "code": 0, "sens": "fusionne", "main_avant": "1" * 40, "main_apres": "2" * 40, "branches": [], "ecartees": [],
            "duree_min": 15, "suite": "rien", "politique": [], "essai": False, "arret": False, "n": 1}


class RetardDesCopiesFigees(unittest.TestCase):
    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.donnees = Path(dossier.name)
        patcher = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.donnees)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.note = self.donnees / "outils-figes-en-retard"

    def test_sans_note_rien_n_est_signale_et_la_ligne_est_celle_d_avant(self):
        self.assertIsNone(train_auto.frozen_late_command({"sommet_train": SOMMET}))
        self.assertTrue(train_auto.report_line(rapport(), None).endswith("| 15 min | rien |"))

    def test_la_note_du_train_du_passage_donne_la_commande(self):
        self.note.write_text(f"{SOMMET} {COMMANDE}\n", encoding="utf-8")
        self.assertEqual(train_auto.frozen_late_command({"sommet_train": SOMMET}), COMMANDE)

    def test_le_rapport_signale_le_retard_avec_la_commande_exacte(self):
        ligne = train_auto.report_line(rapport(), None, retard=COMMANDE)
        self.assertIn("| 15 min | rien ; copies figées en retard sur main, à rafraîchir par l'auteur : " + COMMANDE + " |", ligne)

    def test_une_note_d_un_autre_train_n_est_pas_signalee(self):
        self.note.write_text(f"{'d' * 40} {COMMANDE}\n", encoding="utf-8")
        self.assertIsNone(train_auto.frozen_late_command({"sommet_train": SOMMET}))

    def test_sans_enregistrement_du_train_la_note_n_est_pas_reprise(self):
        # R-20261110-04 : la note n'est reprise que pour le train du passage, jamais quand le passage n'a pas d'enregistrement de train.
        self.note.write_text(f"{SOMMET} {COMMANDE}\n", encoding="utf-8")
        self.assertIsNone(train_auto.frozen_late_command(None))
        self.assertIsNone(train_auto.frozen_late_command({}))

    def test_une_note_en_octets_invalides_est_ignoree_sans_exception(self):
        self.note.write_bytes(b"\xff\xfe\x80 " + COMMANDE.encode("utf-8") + b"\n")
        self.assertIsNone(train_auto.frozen_late_command({"sommet_train": SOMMET}))

    def test_une_note_qui_est_un_dossier_est_ignoree(self):
        self.note.mkdir()
        self.assertIsNone(train_auto.frozen_late_command({"sommet_train": SOMMET}))

    def _publier(self, train_row):
        rec = {"mode": "fusion", "train": {"code": 0, "duree": 60}, "retenues": [], "main": "1" * 40, "paris": "2026-11-10 12:05", "notices": []}
        ctx = mock.Mock(train_row=train_row, a_notifier=[], refuses=[], env={})
        lignes = []
        with mock.patch.object(train_auto, "Guard", return_value=None), \
                mock.patch.object(train_auto, "append_report", side_effect=lignes.append), \
                mock.patch.object(train_auto, "send_notification", return_value=True):
            train_auto.publish(ctx, rec)
        return lignes, rec

    def test_publish_reprend_la_note_du_train_du_passage(self):
        self.note.write_text(f"{SOMMET} {COMMANDE}\n", encoding="utf-8")
        lignes, rec = self._publier({"sens": "fusionne", "sommet_train": SOMMET, "main_avant": "1" * 40, "main_apres": "2" * 40})
        self.assertEqual(len(lignes), 1)
        self.assertIn("copies figées en retard sur main, à rafraîchir par l'auteur : " + COMMANDE, lignes[0])
        self.assertEqual(rec["notices"], [])

    def test_publish_sans_enregistrement_de_train_ne_reprend_pas_la_note(self):
        self.note.write_text(f"{SOMMET} {COMMANDE}\n", encoding="utf-8")
        lignes, _ = self._publier(None)
        self.assertEqual(len(lignes), 1)
        self.assertNotIn("copies figées", lignes[0])

    def test_publish_avec_une_note_illisible_ecrit_quand_meme_le_rapport(self):
        self.note.write_bytes(b"\xff\xfe\x80\n")
        lignes, rec = self._publier({"sens": "fusionne", "sommet_train": SOMMET, "main_avant": "1" * 40, "main_apres": "2" * 40})
        self.assertEqual(len(lignes), 1)
        self.assertNotIn("copies figées", lignes[0])
        self.assertEqual(rec["notices"], [])

    def test_une_note_sans_commande_est_ignoree(self):
        self.note.write_text(f"{SOMMET}\n", encoding="utf-8")
        self.assertIsNone(train_auto.frozen_late_command({"sommet_train": SOMMET}))

    def test_un_pipe_dans_la_commande_est_echappe(self):
        ligne = train_auto.report_line(rapport(), None, retard="cd /a|b")
        self.assertIn("cd /a\\|b |", ligne)


if __name__ == "__main__":
    unittest.main()
