"""Notification du résumé du matin : porte, mémoire du jour, interrupteur local, passage des arguments (design D2, D7, D10, D15).

Le faux `osascript` (en tête du PATH) journalise ses arguments : aucune notification réelle n'est envoyée.
"""
import json
import stat
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Labo, JOUR, SENTINELLE, bilan  # noqa: E402

TITRE = "PMZilla : résumé du matin"


class Porte(Labo):
    def test_appel_planifie_une_notification_et_memoire(self):
        self.tout_connu()
        code, sortie, _ = self.lancer_planifie(bilans=[bilan(1)])
        self.assertEqual(code, 0)
        appels = self.notifications()
        self.assertEqual(len(appels), 1)
        titre, corps = appels[0][-2:]
        self.assertEqual(titre, TITRE)
        lignes = sortie.splitlines()[1:]
        self.assertEqual(corps, " ; ".join(lignes))
        self.assertEqual(len(corps.split(" ; ")), 4)
        self.assertEqual(json.loads(self.memoire().read_text(encoding="utf-8")), {"date": JOUR})
        self.assertEqual(stat.S_IMODE(self.memoire().stat().st_mode), 0o600)
        self.assertEqual([p.name for p in self.donnees.glob(".*.tmp")], [])

    def test_titre_et_corps_sont_des_arguments_pas_du_texte_de_script(self):
        self.tout_connu()
        self.lancer_planifie(bilans=[bilan(1)])
        appel = self.notifications()[0]
        titre, corps = appel[-2:]
        scripts = appel[:-2]
        self.assertIn("on run argv", " ".join(scripts))
        for texte in scripts:
            self.assertNotIn(titre, texte)
            self.assertNotIn("Veille", texte)
            self.assertNotIn(corps, texte)

    def test_deuxieme_appel_le_meme_jour_code_3(self):
        self.tout_connu()
        self.lancer_planifie(bilans=[])
        code, sortie, _ = self.lancer_planifie(bilans=[])
        self.assertEqual(code, 3)
        self.assertIn("Résumé du matin déjà envoyé aujourd'hui", sortie)
        self.assertEqual(len(self.notifications()), 1)

    def test_deuxieme_appel_en_anglais(self):
        self.lancer_planifie(bilans=[])
        code, sortie, _ = self.lancer_planifie("--language", "en", bilans=[])
        self.assertEqual(code, 3)
        self.assertIn("Morning summary already sent today", sortie)

    def test_la_memoire_d_hier_n_empeche_rien(self):
        self.json("resume-du-matin.json", {"date": "2026-10-13"})
        self.assertEqual(self.lancer_planifie(bilans=[])[0], 0)
        self.assertEqual(len(self.notifications()), 1)
        self.assertEqual(json.loads(self.memoire().read_text(encoding="utf-8")), {"date": JOUR})

    def test_memoire_illisible_ne_bloque_pas(self):
        self.memoire().write_text("pas du json", encoding="utf-8")
        self.assertEqual(self.lancer_planifie(bilans=[])[0], 0)
        self.assertEqual(len(self.notifications()), 1)

    def test_l_option_seule_n_envoie_rien(self):
        code, sortie, _ = self.lancer("--notify", bilans=[])
        self.assertEqual(code, 0)
        self.assertTrue(sortie.startswith(TITRE))
        self.assertEqual(self.notifications(), [])
        self.assertFalse(self.memoire().exists())

    def test_la_variable_seule_n_envoie_rien(self):
        code, _, _ = self.lancer(PMZILLA_SUMMARY_NOTIFY="1", bilans=[])
        self.assertEqual(code, 0)
        self.assertEqual(self.notifications(), [])
        self.assertFalse(self.memoire().exists())

    def test_une_autre_valeur_de_la_variable_n_ouvre_pas_la_porte(self):
        self.lancer("--notify", PMZILLA_SUMMARY_NOTIFY="0", bilans=[])
        self.lancer("--notify", PMZILLA_SUMMARY_NOTIFY="", bilans=[])
        self.assertEqual(self.notifications(), [])

    def test_lancement_de_session_n_ecrit_aucun_fichier(self):
        avant = sorted(p.name for p in self.donnees.iterdir())
        self.lancer(bilans=[bilan(1)])
        self.assertEqual(sorted(p.name for p in self.donnees.iterdir()), avant)

    def test_echec_d_osascript_code_1_et_pas_de_memoire(self):
        code, sortie, _ = self.lancer_planifie(bilans=[], STUB_EXIT="1")
        self.assertEqual(code, 1)
        self.assertIn("Notification macOS impossible", sortie)
        self.assertFalse(self.memoire().exists())

    def test_osascript_absent_code_1(self):
        (self.bin / "osascript").unlink()
        code, sortie, _ = self.lancer_planifie(bilans=[], PATH=str(self.bin))      # ni le vrai osascript, ni aucune notification
        self.assertEqual(code, 1)
        self.assertIn("Notification macOS impossible", sortie)

    def test_echec_d_osascript_en_anglais(self):
        self.assertIn("macOS notification failed", self.lancer_planifie("--language", "en", bilans=[], STUB_EXIT="1")[1])

    def test_memoire_non_ecrite_la_notification_part_avec_un_avertissement(self):
        self.verrouiller_donnees()
        code, sortie, erreur = self.lancer_planifie(bilans=[])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.notifications()), 1)
        self.assertTrue(erreur.strip())
        self.assertNotIn(str(self.tmp), erreur)

    def test_aucune_sentinelle_dans_les_arguments(self):
        self.tout_connu()
        self.lancer_planifie(bilans=[bilan(1)])
        self.assertNotIn(SENTINELLE, self.appels.read_text(encoding="utf-8"))

    def test_le_planificateur_n_envoie_pas_en_anglais_sans_demande(self):
        self.lancer_planifie(bilans=[])
        self.assertEqual(self.notifications()[0][-2], TITRE)


class Interrupteur(Labo):
    def test_sans_reglage_le_resume_part(self):
        self.assertEqual(self.lancer_planifie(bilans=[])[0], 0)
        self.assertEqual(len(self.notifications()), 1)

    def test_interrupteur_pose_code_4_rien_d_envoye_rien_d_ecrit(self):
        (self.donnees / "resume-du-matin-coupe").write_text("", encoding="utf-8")
        avant = sorted(p.name for p in self.donnees.iterdir())
        code, sortie, _ = self.lancer_planifie(bilans=[bilan(1)])
        self.assertEqual(code, 4)
        self.assertIn("Résumé du matin désactivé", sortie)
        self.assertTrue(sortie.startswith(TITRE))      # le résumé est quand même imprimé
        self.assertEqual(self.notifications(), [])
        self.assertEqual(sorted(p.name for p in self.donnees.iterdir()), avant)

    def test_interrupteur_en_anglais(self):
        (self.donnees / "resume-du-matin-coupe").write_text("", encoding="utf-8")
        self.assertIn("Morning summary switched off", self.lancer_planifie("--language", "en", bilans=[])[1])

    def test_lancement_de_session_imprime_quoi_qu_il_en_soit(self):
        (self.donnees / "resume-du-matin-coupe").write_text("", encoding="utf-8")
        code, sortie, _ = self.lancer(bilans=[])
        self.assertEqual(code, 0)
        self.assertTrue(sortie.startswith(TITRE))
        self.assertNotIn("désactivé", sortie)
        self.assertEqual(self.lancer("--notify", bilans=[])[0], 0)

    def test_l_interrupteur_prime_sur_la_memoire(self):
        (self.donnees / "resume-du-matin-coupe").write_text("", encoding="utf-8")
        self.json("resume-du-matin.json", {"date": JOUR})
        self.assertEqual(self.lancer_planifie(bilans=[])[0], 4)


if __name__ == "__main__":
    unittest.main()
