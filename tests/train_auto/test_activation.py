"""
Activation de la fusion automatique, lecture seule (autonomous-trains-merge, tâche 3.4, design D5 et D6) : activation_state, activation_valid, activation_path.

    bash tests/run_all.sh train_auto

Cette tranche ne pose ni `activer` ni `desactiver` : le fichier d'activation est écrit ici par le test, comme le fera la tranche 3. Dossier de données jeté pour
chaque test ; aucun dépôt, aucun réseau.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402
import train_record  # noqa: E402

TIPS = [f"{n}" * 40 for n in "12345"]


def champs_compte(sommet, **surcharge):
    base = {"heure": "2026-11-06T10:00:00Z", "code": 0, "sens": "fusionne", "mode": "manuel", "n": 2, "sommets": ["a" * 40, "b" * 40],
            "sommet_train": sommet, "main_avant": "9" * 40, "main_apres": sommet, "runner": "conteneur", "base": False, "front": True,
            "politique": [], "duree_s": 600, "etape": ""}
    base.update(surcharge)
    return base


class AvecDonnees(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name) / "data"
        self.data.mkdir()
        patcher = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.data)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.dossier = self.data / "train-auto"
        self.fichier = self.dossier / "fusion-active"

    def neuf(self):
        """Un dossier de données neuf (sous-test) : le chemin des fichiers suit."""
        self.data = Path(tempfile.mkdtemp(dir=self._tmp.name))
        os.environ["PMZILLA_LAB_DATA"] = str(self.data)   # restauré par mock.patch.dict en fin de test
        self.dossier = self.data / "train-auto"
        self.fichier = self.dossier / "fusion-active"

    def enregistrer(self, tips=TIPS, **surcharge):
        for tip in tips:
            train_record.append(champs_compte(tip, **surcharge))

    def activer(self, serie=TIPS, mode=0o600, **surcharge):
        self.dossier.mkdir(parents=True, exist_ok=True)
        donnees = {"format": 1, "heure": "2026-11-06T12:00:00Z", "serie": list(serie)}
        donnees.update(surcharge)
        self.fichier.write_text(json.dumps(donnees), encoding="utf-8")
        os.chmod(self.fichier, mode)


class TestChemins(AvecDonnees):
    def test_le_chemin_est_celui_du_dossier_de_donnees_du_passage(self):
        self.assertEqual(train_auto.activation_path(), self.data / "train-auto" / "fusion-active")

    def test_le_dossier_est_celui_de_l_arret(self):
        self.assertEqual(train_auto.activation_path().parent, train_auto.stop_path().parent)


class TestEtat(AvecDonnees):
    def test_absent_sans_fichier_c_est_le_mode_observation(self):
        self.assertEqual(train_auto.activation_state(), "absent")
        self.assertFalse(train_auto.activation_valid())

    def test_valide_quand_chaque_sommet_est_un_enregistrement_compte(self):
        self.enregistrer()
        self.activer()
        self.assertEqual(train_auto.activation_state(), "valide")
        self.assertTrue(train_auto.activation_valid())

    def test_invalide_sans_journal_des_trains(self):
        self.activer()
        self.assertEqual(train_auto.activation_state(), "invalide")
        self.assertFalse(train_auto.activation_valid())

    def test_invalide_quand_un_sommet_manque_au_journal(self):
        self.enregistrer(TIPS[:4])
        self.activer()
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_un_enregistrement_n_est_pas_compte(self):
        for surcharge in ({"mode": "auto"}, {"code": 70, "sens": "refuse"}, {"sens": "essai"}, {"runner": "remplace"}):
            with self.subTest(surcharge=surcharge):
                self.neuf()
                self.enregistrer(TIPS[:4])
                self.enregistrer(TIPS[4:], **surcharge)
                self.activer()
                self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_la_serie_n_a_pas_cinq_sommets(self):
        self.enregistrer()
        self.activer(serie=TIPS[:4])
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_la_serie_a_un_doublon(self):
        self.enregistrer()
        self.activer(serie=TIPS[:4] + [TIPS[0]])
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_un_sommet_n_est_pas_un_sha(self):
        self.enregistrer()
        self.activer(serie=TIPS[:4] + ["feat/x"])
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_le_format_est_inconnu(self):
        self.enregistrer()
        self.activer(format=2)
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_l_heure_est_hors_forme(self):
        self.enregistrer()
        self.activer(heure="hier")
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_le_fichier_n_est_pas_du_json(self):
        self.enregistrer()
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.fichier.write_text("pas du json", encoding="utf-8")
        os.chmod(self.fichier, 0o600)
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_le_fichier_est_lisible_par_d_autres(self):
        self.enregistrer()
        self.activer(mode=0o644)
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_le_fichier_est_un_lien(self):
        self.enregistrer()
        self.activer()
        cible = self.dossier / "cible"
        self.fichier.rename(cible)
        self.fichier.symlink_to(cible)
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_le_fichier_est_un_dossier(self):
        self.fichier.mkdir(parents=True)
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_invalide_quand_le_journal_des_trains_est_illisible(self):
        self.enregistrer()
        self.activer()
        with train_record.record_path().open("a", encoding="utf-8") as f:
            f.write("pas du json\n")
        self.assertEqual(train_auto.activation_state(), "invalide")

    def test_un_fichier_disparu_est_inactif_et_n_est_jamais_recree(self):
        self.enregistrer()
        self.activer()
        self.assertTrue(train_auto.activation_valid())
        self.fichier.unlink()
        self.assertFalse(train_auto.activation_valid())
        self.assertEqual(train_auto.activation_state(), "absent")
        self.assertFalse(self.fichier.exists())


class TestLectureSeule(AvecDonnees):
    def test_aucun_fichier_cree_ou_modifie(self):
        self.enregistrer()
        self.activer()
        avant = {p: p.stat().st_mtime_ns for p in self.data.rglob("*") if p.is_file()}
        train_auto.activation_state()
        train_auto.activation_valid()
        apres = {p: p.stat().st_mtime_ns for p in self.data.rglob("*") if p.is_file()}
        self.assertEqual(apres, avant)

    def test_sans_dossier_de_donnees_rien_n_est_cree(self):
        train_auto.activation_state()
        self.assertFalse(self.dossier.exists())


class TestRecordCounted(unittest.TestCase):
    def test_compte_seulement_un_train_de_l_auteur_fusionne_sur_le_conteneur(self):
        self.assertTrue(train_auto.record_counted(champs_compte("a" * 40)))
        for surcharge in ({"mode": "auto"}, {"code": 69}, {"sens": "essai"}, {"runner": "remplace"}):
            self.assertFalse(train_auto.record_counted(champs_compte("a" * 40, **surcharge)), surcharge)
        self.assertFalse(train_auto.record_counted(None))


if __name__ == "__main__":
    unittest.main()
