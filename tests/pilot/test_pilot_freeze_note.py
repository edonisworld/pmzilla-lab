"""`pilot.py freeze` et `pilot.py note` (change multi-session-piloting, design D3, D4, D6, D11) : le contrôle du gel, l'attente, le verrou
périmé, les notes de passage de relais et leur garde. Écrits avant le code.

    python3 -W ignore -m unittest discover -s tests/pilot -q
"""
import os
import stat
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aide_pilot as A  # noqa: E402


def contenu_verrou(labo):
    d = labo.commun / A.NOM_LOCK
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(d.iterdir())} if d.is_dir() else None


class Gel(unittest.TestCase):
    def setUp(self):
        self.labo = A.Labo()

    def test_fin_en_cours(self):
        debut = int(time.time()) - 300
        self.labo.poser_verrou(debut=debut)
        avant = contenu_verrou(self.labo)
        r = self.labo.pilot("freeze", "--check")
        self.assertEqual(r.returncode, 4)
        self.assertIn(f"pilot : fin de branche en cours (feat/autre, depuis {self.labo.heure(debut)})", r.stderr)
        self.assertEqual(contenu_verrou(self.labo), avant)
        self.assertNotIn(A.JETON, r.stdout + r.stderr)

    def test_l_appelant_est_la_fin(self):
        self.labo.poser_verrou()
        r = self.labo.pilot("freeze", "--check", env=self.labo.env(FINISH_LOCK_TOKEN=A.JETON))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot : aucune fin de branche en cours", r.stdout)

    def test_autre_jeton_refuse(self):
        self.labo.poser_verrou()
        r = self.labo.pilot("freeze", "--check", env=self.labo.env(FINISH_LOCK_TOKEN="autre-jeton"))
        self.assertEqual(r.returncode, 4)

    def test_aucun_verrou_et_rien_cree(self):
        r = self.labo.pilot("freeze", "--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot : aucune fin de branche en cours", r.stdout)
        self.assertFalse((self.labo.commun / A.NOM_LOCK).exists())

    def test_verrou_perime_processus_mort(self):
        self.labo.poser_verrou(pid=A.processus_mort())
        avant = contenu_verrou(self.labo)
        r = self.labo.pilot("freeze", "--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot : verrou de fin périmé, ignoré", r.stdout + r.stderr)
        self.assertEqual(contenu_verrou(self.labo), avant)

    def test_verrou_perime_trop_vieux(self):
        maintenant = int(time.time())
        self.labo.poser_verrou(debut=maintenant - 100)
        r = self.labo.pilot("freeze", "--check", env=self.labo.env(PMZILLA_FINISH_LOCK_MAX_AGE="10", PILOT_NOW=str(maintenant)))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot : verrou de fin périmé, ignoré", r.stdout + r.stderr)
        self.assertTrue((self.labo.commun / A.NOM_LOCK).is_dir())

    def test_verrou_sans_pid_lisible_tenu_puis_perime(self):
        d = self.labo.commun / A.NOM_LOCK
        d.mkdir()
        r = self.labo.pilot("freeze", "--check")
        self.assertEqual(r.returncode, 4, "dossier neuf sans pid : tenu pendant ses premières secondes")
        vieux = time.time() - 120
        os.utime(d, (vieux, vieux))
        r = self.labo.pilot("freeze", "--check")
        self.assertEqual(r.returncode, 0, "dossier ancien sans pid : périmé")
        self.assertIn("périmé", r.stdout + r.stderr)

    def test_attente_verrou_retire(self):
        self.labo.poser_verrou()
        env = self.labo.env(PILOT_POLL_SECONDS="0.05", PILOT_WAIT_UNIT_SECONDS="2")
        p = self.labo.popen("freeze", "--wait", "1", env=env)
        time.sleep(0.2)
        self.labo.retirer_verrou()
        sortie, erreur = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, erreur)
        self.assertIn("pilot : aucune fin de branche en cours", sortie)

    def test_attente_epuisee(self):
        self.labo.poser_verrou()
        env = self.labo.env(PILOT_POLL_SECONDS="0.05", PILOT_WAIT_UNIT_SECONDS="0.3")
        r = self.labo.pilot("freeze", "--wait", "1", env=env)
        self.assertEqual(r.returncode, 4)
        self.assertIn("pilot : fin de branche toujours en cours après 1 min", r.stderr)
        self.assertTrue((self.labo.commun / A.NOM_LOCK).is_dir())

    def test_attente_libre_tout_de_suite(self):
        r = self.labo.pilot("freeze", "--wait", "5", env=self.labo.env(PILOT_POLL_SECONDS="0.05", PILOT_WAIT_UNIT_SECONDS="0.3"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_minutes_hors_limites(self):
        for valeur in ("0", "121", "-3", "abc", "1.5", ""):
            r = self.labo.pilot("freeze", "--wait", valeur)
            self.assertEqual(r.returncode, 2, valeur)
        self.assertEqual(self.labo.pilot("freeze").returncode, 2)
        for valeur in ("1", "60", "120"):
            r = self.labo.pilot("freeze", "--wait", valeur, env=self.labo.env(PILOT_POLL_SECONDS="0.05", PILOT_WAIT_UNIT_SECONDS="0.2"))
            self.assertEqual(r.returncode, 0, valeur)

    def test_anglais(self):
        self.labo.poser_verrou()
        r = self.labo.pilot("--language", "en", "freeze", "--check")
        self.assertEqual(r.returncode, 4)
        self.assertIn("pilot: ", r.stderr)
        self.assertIn("finish", r.stderr)
        self.assertNotIn("fin de branche", r.stderr)

    def test_hors_du_depot(self):
        dehors = self.labo.tmp / "hors-depot"
        dehors.mkdir()
        r = self.labo.pilot("freeze", "--check", cwd=dehors, env=self.labo.env(GIT_CEILING_DIRECTORIES=str(self.labo.tmp)))
        self.assertEqual(r.returncode, 3)


class Notes(unittest.TestCase):
    def setUp(self):
        self.labo = A.Labo()

    def test_ecrite_et_remplacee(self):
        r = self.labo.pilot("note", A.BRANCHE_PROPRE, "en attente de revue")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot : note enregistrée", r.stdout)
        self.assertEqual(len(self.labo.fichiers_notes()), 1)
        self.labo.pilot("note", A.BRANCHE_PROPRE, "prête pour la fin")
        self.assertEqual(len(self.labo.fichiers_notes()), 1)
        statut = self.labo.pilot("status").stdout
        self.assertIn("note : prête pour la fin", statut)
        self.assertNotIn("en attente de revue", statut)

    def test_stockage_hors_de_git_et_prive(self):
        self.labo.pilot("note", A.BRANCHE_PROPRE, "en attente de revue")
        dossier = self.labo.commun / "pmzilla-notes"
        self.assertEqual(stat.S_IMODE(dossier.stat().st_mode) & 0o077, 0)
        for fichier in dossier.iterdir():
            self.assertEqual(stat.S_IMODE(fichier.stat().st_mode) & 0o077, 0)
            self.assertFalse(fichier.name.startswith("."), "aucun fichier temporaire restant")
        for wt in (self.labo.ws, self.labo.wt_propre):
            self.assertEqual(A.git(wt, "status", "--porcelain"), "")
        self.assertEqual(sorted(p.name for p in self.labo.donnees.iterdir()), ["roadmap-cache.json"])

    def test_retiree(self):
        self.labo.pilot("note", A.BRANCHE_PROPRE, "en attente de revue")
        r = self.labo.pilot("note", A.BRANCHE_PROPRE, "--clear")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot : note retirée", r.stdout)
        self.assertEqual(self.labo.fichiers_notes(), [])
        self.assertNotIn("note :", self.labo.pilot("status").stdout)

    def test_nom_sensible_identifiant_et_cle_de_ticket(self):
        for texte in (f"voir {A.NOM_SENSIBLE} avant la fin", f"voir {A.NOM_SENSIBLE.lower()} avant la fin",
                      f"voir {A.IDENTIFIANT} ici", f"corrige {A.CLE_TICKET} d'abord"):
            r = self.labo.pilot("note", A.BRANCHE_PROPRE, texte)
            self.assertEqual(r.returncode, 5, texte)
            self.assertIn("pilot : note refusée (nom sensible, identifiant ou clé de ticket)", r.stderr)
            for valeur in (A.NOM_SENSIBLE, A.NOM_SENSIBLE.lower(), A.IDENTIFIANT, A.CLE_TICKET):
                self.assertNotIn(valeur, r.stdout + r.stderr)
        self.assertEqual(self.labo.fichiers_notes(), [])

    def test_une_cle_de_feature_n_est_pas_une_cle_de_ticket(self):
        r = self.labo.pilot("note", A.BRANCHE_PROPRE, "suite de R-12")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_garde_impossible_liste_absente(self):
        r = self.labo.pilot("note", A.BRANCHE_PROPRE, "en attente de revue",
                            env=self.labo.env(PMZILLA_LAB_SENSITIVE_NAMES=str(self.labo.tmp / "absente.txt")))
        self.assertEqual(r.returncode, 6)
        self.assertIn("pilot : contrôle de la note impossible", r.stderr)
        self.assertEqual(self.labo.fichiers_notes(), [])

    def test_garde_impossible_liste_vide(self):
        self.labo.noms.write_text("# rien\n", encoding="utf-8")
        r = self.labo.pilot("note", A.BRANCHE_PROPRE, "en attente de revue")
        self.assertEqual(r.returncode, 6)
        self.assertEqual(self.labo.fichiers_notes(), [])

    def test_aucun_worktree(self):
        r = self.labo.pilot("note", "feat/inconnue", "en attente de revue")
        self.assertEqual(r.returncode, 7)
        self.assertIn("pilot : aucun worktree pour la branche feat/inconnue", r.stderr)
        self.assertEqual(self.labo.fichiers_notes(), [])
        r = self.labo.pilot("note", "feat/inconnue", "--clear")
        self.assertEqual(r.returncode, 7)

    def test_texte_trop_long_ou_sur_plusieurs_lignes(self):
        self.assertEqual(self.labo.pilot("note", A.BRANCHE_PROPRE, "x" * 201).returncode, 2)
        self.assertEqual(self.labo.pilot("note", A.BRANCHE_PROPRE, "x" * 200).returncode, 0)
        self.assertEqual(self.labo.pilot("note", A.BRANCHE_PROPRE, "deux\nlignes").returncode, 2)
        self.assertEqual(self.labo.pilot("note", A.BRANCHE_PROPRE).returncode, 2)

    def test_nom_de_fichier_de_la_note(self):
        """Contrat pour la fin de worktree (tâche 7.2) : nom du fichier = branche avec « % » devenu « %25 » puis « / » devenu « %2F »."""
        self.labo.pilot("note", A.BRANCHE_PROPRE, "en attente de revue")
        attendu = A.BRANCHE_PROPRE.replace("%", "%25").replace("/", "%2F")
        self.assertEqual(self.labo.fichiers_notes(), [attendu])

    def test_le_verrou_n_est_ni_cree_ni_retire(self):
        self.labo.pilot("note", A.BRANCHE_PROPRE, "en attente de revue")
        self.assertFalse((self.labo.commun / A.NOM_LOCK).exists())
        self.labo.poser_verrou()
        avant = contenu_verrou(self.labo)
        self.labo.pilot("note", A.BRANCHE_PROPRE, "--clear")
        self.labo.pilot("status")
        self.labo.pilot("freeze", "--check")
        self.assertEqual(contenu_verrou(self.labo), avant)

    def test_aucune_ecriture_git(self):
        avant = self.labo.etat_git()
        self.labo.pilot("note", A.BRANCHE_PROPRE, "en attente de revue")
        self.labo.pilot("note", A.BRANCHE_PROPRE, "--clear")
        self.assertEqual(self.labo.etat_git(), avant)


if __name__ == "__main__":
    unittest.main()
