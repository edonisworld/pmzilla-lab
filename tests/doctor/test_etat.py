"""Option --record (tâches 4.1 et 4.2) : fichier d'état doctor-etat.json et notification, seulement sous le planificateur."""
import json
import os
import stat
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import SENTINELLE, Labo, modeles_du_depot  # noqa: E402


class FichierDEtat(Labo):
    def etat(self):
        return json.loads((self.donnees / "doctor-etat.json").read_text(encoding="utf-8"))

    def test_execution_enregistree(self):
        p = self.lancer("--record")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        chemin = self.donnees / "doctor-etat.json"
        self.assertTrue(chemin.exists())
        self.assertEqual(stat.S_IMODE(chemin.stat().st_mode), 0o600)
        etat = self.etat()
        ids = [c["id"] for c in etat["checks"]]
        self.assertEqual(ids, [ligne.split(" ")[0] for ligne in self.lancer().stdout.splitlines()[:-1]])
        self.assertEqual(etat["version"], 1)
        self.assertEqual(etat["checked_at"], "2026-10-14T10:00")
        self.assertEqual(sum(etat["counts"].values()), len(ids))
        self.assertIsNone(etat["last_notification"])

    def test_ni_chemin_ni_branche_ni_modele_ni_secret(self):
        self.ajouter_branche("feat/fusionnee", fusionnee=True, worktree=True)
        self.fermer_base()
        self.ollama.modeles = []
        self.lancer("--record")
        texte = (self.donnees / "doctor-etat.json").read_text(encoding="utf-8")
        for interdit in [str(self.base), str(self.maison), "/Users/", "feat/fusionnee", SENTINELLE, "com.pmzilla", *modeles_du_depot(), "127.0.0.1"]:
            self.assertNotIn(interdit, texte)

    def test_remplacement_atomique_sans_reste(self):
        self.lancer("--record")
        self.lancer("--record")
        self.assertEqual(sorted(p.name for p in self.donnees.iterdir() if p.name.startswith("doctor-etat")), ["doctor-etat.json"])

    def test_le_code_de_sortie_suit_les_controles(self):
        self.fermer_base()
        self.assertEqual(self.lancer("--record").returncode, 1)
        self.assertEqual(self.etat()["counts"]["problem"], 1)

    def test_dossier_non_inscriptible_code_2(self):
        os.chmod(self.donnees, 0o500)
        self.addCleanup(os.chmod, self.donnees, 0o700)
        p = self.lancer("--record")
        self.assertEqual(p.returncode, 2)
        self.assertIn("doctor : impossible de lancer", p.stderr + p.stdout)
        self.assertIn("doctor: cannot run", self.lancer("--record", "--language", "en").stderr)

    def test_sans_record_aucun_fichier_d_etat(self):
        self.lancer()
        self.lancer("--json")
        self.assertFalse((self.donnees / "doctor-etat.json").exists())

    def test_un_etat_precedent_illisible_est_remplace(self):
        (self.donnees / "doctor-etat.json").write_text("{pas du json", encoding="utf-8")
        self.assertEqual(self.lancer("--record").returncode, 0)
        self.assertEqual(self.etat()["version"], 1)


class Notification(Labo):
    def notifications(self):
        return [a for a in self.appels() if a.startswith("osascript")]

    def lancer_planifie(self, *args, env=None):
        return self.lancer("--record", *args, env={"DOCTOR_NOTIFIER": "1", **(env or {})})

    def deux_problemes(self):
        self.fermer_base()
        self.ollama.arreter()

    def test_deux_problemes_deux_passages_une_seule_notification(self):
        self.deux_problemes()
        self.lancer_planifie()
        self.lancer_planifie()
        notifications = self.notifications()
        self.assertEqual(len(notifications), 1)
        self.assertIn("PMZilla doctor : 2 problème(s) : db, ollama", notifications[0])
        self.assertEqual(json.loads((self.donnees / "doctor-etat.json").read_text())["last_notification"], "2026-10-14")

    def test_texte_en_anglais(self):
        self.deux_problemes()
        self.lancer_planifie("--language", "en")
        self.assertIn("PMZilla doctor: 2 problem(s): db, ollama", self.notifications()[0])

    def test_le_lendemain_une_nouvelle_notification(self):
        self.deux_problemes()
        self.lancer_planifie()
        self.lancer_planifie(env={"PMZILLA_LAB_TODAY": "2026-10-15"})
        self.assertEqual(len(self.notifications()), 2)

    def test_lancement_a_la_main_aucune_notification(self):
        self.deux_problemes()
        self.lancer("--record")
        self.lancer()
        self.assertEqual(self.notifications(), [])

    def test_variable_sans_record_aucune_notification(self):
        self.deux_problemes()
        self.lancer(env={"DOCTOR_NOTIFIER": "1"})
        self.assertEqual(self.notifications(), [])

    def test_avertissement_seul_aucune_notification(self):
        self.lancer_planifie(env={"DOCTOR_DISK_FREE_GB": "12"})
        self.assertEqual(self.notifications(), [])

    def test_aucun_probleme_aucune_notification(self):
        self.lancer_planifie()
        self.assertEqual(self.notifications(), [])

    def test_la_date_de_derniere_notification_survit_a_un_passage_sain(self):
        import socket
        from aide_doctor import FauxOllama
        self.deux_problemes()
        self.lancer_planifie()
        sain = socket.socket()
        sain.bind(("127.0.0.1", 0))
        sain.listen(5)
        self.addCleanup(sain.close)
        ollama = FauxOllama(modeles_du_depot())
        self.addCleanup(ollama.arreter)
        p = self.lancer_planifie(env={"PMZILLA_LAB_DB_PORT": sain.getsockname()[1], "DOCTOR_OLLAMA_URL": ollama.url()})
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual(json.loads((self.donnees / "doctor-etat.json").read_text())["last_notification"], "2026-10-14")

    def test_texte_sans_chemin_branche_modele_ni_secret(self):
        self.ajouter_branche("feat/fusionnee", fusionnee=True, worktree=True)
        self.deux_problemes()
        self.lancer_planifie()
        texte = self.notifications()[0]
        for interdit in [str(self.base), "feat/fusionnee", SENTINELLE, *modeles_du_depot()]:
            self.assertNotIn(interdit, texte)

    def test_echec_de_osascript_ne_change_pas_le_code(self):
        self.deux_problemes()
        (self.bin / "osascript").write_text('#!/bin/sh\necho "osascript $*" >> "$STUB_LOG"\nexit 1\n', encoding="utf-8")
        self.assertEqual(self.lancer_planifie().returncode, 1)


if __name__ == "__main__":
    unittest.main()
