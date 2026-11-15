"""Contrôle ci-container (R-20261103-6, Q9) : Colima tourne-t-il, et l'image de CI de la clé courante existe-t-elle. Les commandes sont des
doublures en tête du PATH (colima) et DOCTOR_CI_LOCAL (remplace `bash tools/ci_local.sh cle`, qui reçoit « cle ») ; aucun Docker, aucun
Colima réel, aucune lecture de la vraie image."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import Labo, TOOLS  # noqa: E402

import doctor  # noqa: E402
import doctor_messages  # noqa: E402


class ControleCiContainer(Labo):
    def cle(self, env=None):
        niveau, entree, _ = self.niveau("ci-container", env=env)
        return niveau, entree["reason"]["key"]

    def lignes(self, langue="fr", env=None):
        sortie = self.lancer("--language", langue, env=env).stdout
        return [ligne for ligne in sortie.splitlines() if ligne.startswith("ci-container")]

    def test_colima_tourne_et_image_presente_ok(self):
        self.assertEqual(self.cle(), ("ok", "ok"))
        self.assertEqual(self.lignes(), ["ci-container : ok : Colima tourne et l'image de CI de la clé courante existe"])
        self.assertEqual(self.lignes("en"), ["ci-container: ok: Colima is running and the CI image of the current key exists"])

    def test_la_commande_de_l_image_recoit_cle_et_colima_status(self):
        self.lancer()
        appels = self.appels()
        self.assertIn("colima status", appels)
        self.assertIn("ci_local cle", appels)

    def test_colima_arrete_avertit_avec_la_commande_et_ne_cherche_pas_l_image(self):
        env = {"FAUX_COLIMA_CODE": "1"}
        niveau, entree, p = self.niveau("ci-container", env=env)
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "colima_stopped"))
        self.assertEqual(p.returncode, 0)
        self.assertIn("colima start --cpu 8 --memory 16", self.lignes(env=env)[0])
        self.assertIn("colima start --cpu 8 --memory 16", self.lignes("en", env=env)[0])
        self.assertNotIn("ci_local cle", self.appels())

    def test_image_absente_avertit_avec_la_commande(self):
        env = {"FAUX_CI_LOCAL_CODE": "5"}
        niveau, entree, p = self.niveau("ci-container", env=env)
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "image_absent"))
        self.assertEqual(p.returncode, 0)
        self.assertIn("bash tools/ci_local.sh up", self.lignes(env=env)[0])
        self.assertIn("bash tools/ci_local.sh up", self.lignes("en", env=env)[0])

    def test_autre_code_de_la_commande_image_illisible(self):
        for code in ("3", "4", "126"):
            with self.subTest(code=code):
                self.assertEqual(self.cle(env={"FAUX_CI_LOCAL_CODE": code}), ("warning", "image_unreadable"))

    def test_colima_introuvable_ignore(self):
        self.assertEqual(self.cle(env={"FAUX_COLIMA_ABSENT": "1"}), ("skipped", "colima_missing"))
        self.assertEqual(self.lignes(env={"FAUX_COLIMA_ABSENT": "1"}), ["ci-container : ignoré : commande colima introuvable"])

    def test_colima_absent_du_path_ou_en_delai(self):
        ctx = doctor.Contexte(__import__("datetime").date(2026, 11, 3), __import__("datetime").time(9, 0), self.donnees,
                              self.journaux, self.maison, {})
        with mock.patch.object(doctor.subprocess, "run", side_effect=FileNotFoundError("colima")):
            self.assertEqual(doctor.etat_colima(), "missing")
            self.assertEqual(doctor.controle_ci_container(ctx, []).cle, "colima_missing")
        with mock.patch.object(doctor.subprocess, "run", side_effect=doctor.subprocess.TimeoutExpired("colima", 15)):
            self.assertEqual(doctor.etat_colima(), "stopped")
            self.assertEqual(doctor.controle_ci_container(ctx, []).cle, "colima_stopped")

    def test_commande_de_l_image_en_delai_illisible(self):
        ctx = doctor.Contexte(__import__("datetime").date(2026, 11, 3), __import__("datetime").time(9, 0), self.donnees,
                              self.journaux, self.maison, {})
        with mock.patch.object(doctor, "etat_colima", return_value="ok"), \
                mock.patch.object(doctor.subprocess, "run", side_effect=doctor.subprocess.TimeoutExpired("bash", 60)):
            self.assertIsNone(doctor.code_image_ci(ctx))
            self.assertEqual(doctor.controle_ci_container(ctx, []).cle, "image_unreadable")

    def test_sans_couture_la_commande_est_ci_local_cle_de_l_arbre_du_doctor(self):
        """Sans DOCTOR_CI_LOCAL : `bash <tools>/ci_local.sh cle`, lancé depuis la racine du dépôt (la clé est celle de ce dépôt)."""
        ctx = doctor.Contexte(__import__("datetime").date(2026, 11, 3), __import__("datetime").time(9, 0), self.donnees,
                              self.journaux, self.maison, {})
        with mock.patch.object(doctor.subprocess, "run") as run:
            run.return_value.returncode = 5
            self.assertEqual(doctor.code_image_ci(ctx), 5)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["bash", str(TOOLS / "ci_local.sh"), "cle"])
        self.assertEqual(kwargs["cwd"], str(TOOLS.parent))

    def test_ne_lance_aucune_commande_qui_ecrit_et_n_ecrit_rien(self):
        avant = self.fichiers()
        self.lancer(env={"FAUX_CI_LOCAL_CODE": "5"})
        self.assertEqual(self.fichiers(), avant)
        self.assertEqual([a for a in self.appels() if a.startswith("colima") and a != "colima status"], [])
        self.assertEqual([a for a in self.appels() if a.startswith("ci_local") and a != "ci_local cle"], [])
        self.assertEqual([a for a in self.appels() if a.startswith(("INTERDIT", "docker"))], [])

    def test_catalogues_et_etat_sans_chemin(self):
        for cle in ("ok", "colima_missing", "colima_stopped", "image_absent", "image_unreadable"):
            for langue in ("fr", "en"):
                self.assertIn(f"raison_ci_container_{cle}", doctor_messages.CATALOGS[langue])
        self.assertIn(("ci-container", "image_absent"), doctor.TOUTES_LES_RAISONS)
        self.assertIn("ci-container", doctor.ORDRE)
        self.lancer("--record", env={"FAUX_CI_LOCAL_CODE": "5"})
        texte = (self.donnees / "doctor-etat.json").read_text(encoding="utf-8")
        self.assertNotIn(str(self.bin), texte)
        etat = json.loads(texte)
        self.assertIn("ci-container", [c["id"] for c in etat["checks"]])

    def test_garde_neuve_dit_ce_qu_elle_remplace_et_son_retrait(self):
        source = (TOOLS / "doctor.py").read_text(encoding="utf-8")
        self.assertIn("Garde neuve (R-20261103-6, Q9). Remplace : rien. Retrait : permanent, tant que la preuve passe par le conteneur.", source)


if __name__ == "__main__":
    unittest.main()
