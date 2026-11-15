"""
Tâche 2.3 (change autonomous-trains-observe) : les contrôles du passage, un test chacun, dans l'ordre de D2. Chaque test montre que les contrôles
suivants ne tournent pas (les faux gardes consignent leurs appels, le faux git espion consigne `ls-remote`). Horloge imposée (TRAIN_AUTO_NOW),
dépôts jetables, aucun réseau.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from aide_auto import AvecAuto, RACINE, epoch

sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402


def processus_mort():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


class Controles(AvecAuto):
    def attente(self, r, code_raison, libelle_fr):
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn(f"train_auto : attente : {libelle_fr}", r.sortie)
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"]), ("attente", code_raison))
        self.assertEqual(d["retenues"], [])
        self.assertIsNone(d["essai"])

    def appels_ls_remote(self):
        return [l for l in self.t.journal_git() if " ls-remote " in f" {l} "]

    def rien_apres(self, *controles):
        for c in controles:
            if c == "matin":
                self.assertEqual(self.t.appels("matin"), [])
            elif c == "crochets":
                self.assertEqual(self.t.appels("crochets"), [])
            elif c == "distant":
                self.assertEqual(self.appels_ls_remote(), [])
            elif c == "dossier":
                self.assertEqual(self.t.appels("update appelé"), [])

    # --- 1. l'arrêt d'urgence
    def test_1_arret_d_urgence(self):
        self.assertEqual(self.auto("arret").code, 0)
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : arrêté (arrêt d'urgence actif)", r.sortie)
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"]), ("arrete", "arret"))
        self.rien_apres("matin", "crochets", "distant", "dossier")

    # --- 2. hors session
    def test_2_session_refusee_avant_tout_verrou(self):
        r = self.passage(extra={"CLAUDECODE": "1"})
        self.assertEqual(r.code, 3, r.texte)
        self.assertIn("train_auto : session Claude Code, lancement refusé", r.texte)
        self.assertEqual(self.journal(), [])
        self.assertFalse((self.dossier_train() / "passage.lock").exists())
        self.assertFalse(self.fichier_liste().exists())
        self.rien_apres("matin", "crochets", "distant", "dossier")

    def test_2_marqueur_vide_compte_comme_pose(self):
        r = self.passage(extra={"CLAUDECODE": ""})
        self.assertEqual(r.code, 3, r.texte)

    def test_2_appelant_launchd_ou_terminal(self):
        self.assertEqual(self.passage(now=epoch(7, 0)).code, 0)
        self.assertEqual(self.dernier()["caller"], "terminal")
        self.assertEqual(self.passage(now=epoch(7, 0), extra={"XPC_SERVICE_NAME": train_auto.LABEL}).code, 0)
        self.assertEqual(self.dernier()["caller"], "launchd")

    # --- 3. la fenêtre
    # Passages toutes les heures de 8 h à 21 h (autonomous-trains-merge D13, R-20261101-83, tâche 9.6) : ces quatre tests, écrits pour les deux passages de 12 h et de
    # 17 h 30 d'autonomous-trains-observe, sont réécrits sur les nouvelles heures (même assertion : hors de toute fenêtre, fenêtre atteinte).
    def test_3_avant_la_fenetre(self):
        r = self.passage(now=epoch(7, 30))
        self.attente(r, "hors-fenetre", "hors fenêtre")
        self.rien_apres("matin", "crochets", "distant", "dossier")

    def test_3_entre_les_fenetres_apres_la_tolerance(self):
        self.attente(self.passage(now=epoch(13, 30)), "hors-fenetre", "hors fenêtre")
        self.attente(self.passage(now=epoch(22, 0)), "hors-fenetre", "hors fenêtre")

    def test_3_apres_l_heure_de_depart_la_plus_tardive(self):
        self.attente(self.passage(now=epoch(12, 26)), "hors-fenetre", "hors fenêtre")
        self.attente(self.passage(now=epoch(17, 26)), "hors-fenetre", "hors fenêtre")

    def test_3_dans_une_fenetre(self):
        r = self.passage(now=epoch(17, 10))
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.dernier()["fenetre"], "17:00")

    def test_3_quatorze_passages_de_8_h_a_21_h(self):
        self.assertEqual(len(train_auto.WINDOWS), 14)
        self.assertEqual(train_auto.WINDOWS[0], ("08:00", "08:25"))
        self.assertEqual(train_auto.WINDOWS[-1], ("21:00", "21:25"))
        self.assertEqual(train_auto.TOLERANCE_MINUTES, 30)
        self.assertEqual(train_auto.RETRY_SECONDS, 300)

    # --- 4. l'état du matin
    def test_4_etat_du_matin_non_verifie(self):
        (self.t.etat / "matin-refuse").write_text("x", encoding="utf-8")
        r = self.passage()
        self.attente(r, "matin", "veille ou sauvegarde du jour en cours")   # R-20261102-3 et R-20261102-5 (D4), réécrit : phrase
        self.assertEqual(len(self.t.appels("matin")), 1)
        self.rien_apres("crochets", "distant", "dossier")

    # --- 5. les verrous
    def test_5_verrou_de_fin_tenu_pendant_toute_la_tolerance(self):
        self.t.verrou_etranger()
        r = self.passage()
        self.attente(r, "verrou-fin", "verrou de fin tenu")
        self.rien_apres("distant", "crochets", "dossier")

    def test_5_verrou_de_fin_libere_dans_la_tolerance(self):
        dossier = self.t.verrou_etranger()
        proc = subprocess.Popen([sys.executable, "-I", str(train_auto.__file__), "pass"], cwd=self.t.lab,
                                # six essais espacés de 5 s réelles : une fenêtre de 30 s réelles au lieu de 6, large devant un test ralenti
                                env=self.environnement(epoch(), {"TRAIN_AUTO_REAL_SLEEP": "5"}), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(1.5)
        self.assertIsNone(proc.poll(), "le passage aurait dû attendre tant que le verrou de fin est tenu")
        shutil.rmtree(dossier)
        sortie, erreur = proc.communicate(timeout=300)
        self.assertEqual(proc.returncode, 0, sortie + erreur)
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"]), ("rien", "liste-vide"))   # les contrôles suivants ont tourné

    def test_5_ancien_verrou_du_runner_de_session_tenu_par_un_processus_vivant_ne_fait_plus_attendre(self):
        # tooling-proof-in-container, T2 (D3, R-20261104-7 P2, tâche 6.8) : l'attente du verrou du runner de session est retirée ; seul le verrou de fin
        # fait attendre (test_5_verrou_de_fin_tenu_pendant_toute_la_tolerance). Remplace test_5_runner_de_session_tenu_par_un_processus_vivant (retiré).
        verrou = self.t.data / "verrous" / "run-all-session"
        verrou.mkdir(parents=True)
        (verrou / "pid").write_text(str(os.getpid()), encoding="utf-8")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual((self.dernier()["decision"], self.dernier()["raison"]), ("rien", "liste-vide"))   # les contrôles suivants ont tourné
        self.assertNotIn("runner-session", r.texte)
        self.assertNotIn("runner-session", (self.t.data / "train-auto" / "journal.jsonl").read_text(encoding="utf-8"))
        self.assertFalse(hasattr(train_auto, "session_runner_held"), "la fonction du contrôle retiré n'existe plus")

    def test_5_runner_de_session_tenu_par_un_processus_mort(self):
        # T2 (6.8) : le mécanisme de reprise d'un verrou mort n'existe plus côté train (main le reprenait : ignoré). Objet distinct du test précédent : un
        # verrou ancien d'un processus MORT n'est ni lu pour attendre, ni repris, ni retiré, ni cité par le train (il appartient au lanceur d'avant T2).
        verrou = self.t.data / "verrous" / "run-all-session"
        verrou.mkdir(parents=True)
        mort = str(processus_mort())
        (verrou / "pid").write_text(mort, encoding="utf-8")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual((self.dernier()["decision"], self.dernier()["raison"]), ("rien", "liste-vide"))
        self.assertEqual((verrou / "pid").read_text(encoding="utf-8"), mort, "le train ne touche pas à l'ancien verrou")
        self.assertNotIn("runner-session", (self.t.data / "train-auto" / "journal.jsonl").read_text(encoding="utf-8"))

    # --- 6. l'espace de travail, le distant et le dossier d'exécution
    def test_6_espace_de_travail_pas_propre(self):
        (self.t.contenu / "brouillon.txt").write_text("x\n", encoding="utf-8")
        r = self.passage()
        self.attente(r, "espace-de-travail", "espace de travail pas sur main ou pas propre")
        self.rien_apres("distant", "crochets", "dossier")

    def test_6_espace_de_travail_pas_sur_main(self):
        self.t.git("checkout", "-q", "-b", "autre")
        self.attente(self.passage(), "espace-de-travail", "espace de travail pas sur main ou pas propre")

    def test_6_ls_remote_en_echec(self):
        self.t.git("remote", "set-url", "origin", str(self.t.dossier / "inexistant.git"))
        self.attente(self.passage(), "distant", "distant injoignable")
        self.assertEqual(len(self.appels_ls_remote()), 1)
        self.rien_apres("crochets", "dossier")

    def test_6_ls_remote_depasse_son_delai(self):
        # faux git de ce test seulement : `ls-remote` dort 60 s ; le passage réel borne l'appel à REMOTE_TIMEOUT (ici deux secondes) ; la borne du test
        # (15 s, filet) reste très en dessous du sommeil du faux (60 s) ; le vrai verdict est le témoin absent (R-20261101-108) : le faux l'écrit seulement
        # s'il va au bout de son sommeil, donc seulement si l'appel n'a pas été interrompu
        faux = Path(self.temp.name) / "faux-git"
        faux.mkdir()
        temoin = faux / "sommeil-termine"
        script = faux / "git"
        script.write_text(f'#!/bin/sh\ncase " $* " in *" ls-remote "*) sleep 60; : > "{temoin}" 2>/dev/null; exit 0 ;; esac\nexec "{self.t.git_reel}" "$@"\n', encoding="utf-8")
        script.chmod(0o755)
        env = dict(os.environ, PATH=f"{faux}:{os.environ.get('PATH', '')}")
        with mock.patch.dict(os.environ, env), mock.patch.object(train_auto, "REMOTE_TIMEOUT", 2):
            ctx = train_auto.Context(os.environ, self.t.contenu, self.t.run)
            debut = time.time()
            self.assertIsNone(train_auto.remote_main(ctx))   # délai dépassé : aucune référence rendue
            self.assertFalse(temoin.exists(), "le faux ls-remote a fini son sommeil : l'appel n'a pas été interrompu")   # vérifié juste après l'appel ; un témoin tardif tombe dans le dossier temporaire du test
            self.assertLess(time.time() - debut, 15)

    def test_6_main_local_different_du_distant_sans_fetch(self):
        autre = self.t.cloner_ailleurs()
        self.t.git("commit", "-q", "--allow-empty", "-m", "ailleurs", cwd=autre)
        self.t.git("push", "-q", "origin", "main", cwd=autre)
        avant = self.t.origin_main()
        r = self.passage()
        self.attente(r, "main-different", "main local différent du distant")
        self.assertEqual(self.t.origin_main(), avant, "origin/main n'a pas bougé : aucun fetch")
        self.assertEqual([l for l in self.t.journal_git() if " fetch" in f" {l}"], [])
        self.rien_apres("crochets", "dossier")

    def test_6_dossier_d_execution_pas_a_jour(self):
        r = self.passage(extra={"FAKE_RUN_UPDATE": "echec"})
        self.attente(r, "dossier-execution", "dossier d'exécution pas à jour")
        self.rien_apres("crochets")

    # --- 7. les crochets et l'identité
    def test_7_crochets_non_verifies(self):
        (self.t.etat / "crochets-ko").write_text("x", encoding="utf-8")
        self.attente(self.passage(), "crochets", "crochets non vérifiés")

    def test_7_identite_git_absente(self):
        self.t.sans_identite()
        self.attente(self.passage(), "identite", "identité Git absente")

    def test_7_controle_doctor_absent_note_sans_bloquer(self):
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        d = self.dernier()
        self.assertEqual(d["doctor"], "absent")
        self.assertEqual(d["decision"], "rien")   # le passage est allé jusqu'à la liste

    def test_le_premier_echec_arrete_tout(self):
        # matin refusé ET crochets en échec : seule la première raison est journalisée
        (self.t.etat / "matin-refuse").write_text("x", encoding="utf-8")
        (self.t.etat / "crochets-ko").write_text("x", encoding="utf-8")
        self.attente(self.passage(), "matin", "veille ou sauvegarde du jour en cours")   # R-20261102-3 et R-20261102-5 (D4), réécrit : phrase


if __name__ == "__main__":
    unittest.main()
