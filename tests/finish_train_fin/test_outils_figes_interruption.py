"""
Niveau 2 du bac à sable de Bash, décision R-20261110-05 : SIGINT (Ctrl-C) ou SIGHUP (terminal fermé) reçu PENDANT la question « Rafraîchir les copies figées du bac à sable ?
(o/n) » de tools/finish_train.sh vaut « n » : aucune copie, la note du retard est écrite, le train poursuit sa fin normale (dossier d'exécution mis à jour, verrou rendu,
journal écrit) et garde son code de sortie (0 après une fusion réussie). Hors de cette question, les pièges généraux (130, 129) restent ceux du script.
Dépôts jetables de l'aide commune (aide_train) ; mêmes dépôts que test_outils_figes_retard.py. Remplace : rien. Retrait : avec le bac à sable.
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, BASH, OUTILS, _signaux_par_defaut  # noqa: E402

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


class InterruptionPendantLaQuestion(AvecJournal):
    def setUp(self):
        super().setUp()
        self.t.sans_substitution = True
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

    def lancer_jusqu_a_la_question(self):
        """Lance le train, répond « o » à la question d'arrivée, attend que la question des copies figées soit affichée (l'entrée reste ouverte).
        Rend (processus, fichier de sortie) : l'appelant envoie ensuite sa réponse ou son signal, jamais avant l'affichage."""
        sortie = self.t.dossier / "sortie-interruption.txt"
        with open(sortie, "w", encoding="utf-8") as f:
            proc = subprocess.Popen([BASH, str(self.t.script()), "feat/x"], cwd=self.t.lab, env=self.t.env(None), stdin=subprocess.PIPE, stdout=f,
                                    stderr=subprocess.STDOUT, text=True, start_new_session=True, preexec_fn=_signaux_par_defaut)
        self.addCleanup(self.tuer, proc)
        proc.stdin.write("o\n")
        proc.stdin.flush()
        fin = time.time() + 120
        while QUESTION not in sortie.read_text(encoding="utf-8", errors="replace"):
            if proc.poll() is not None:
                self.fail(f"le train s'est arrêté (code {proc.returncode}) avant la question des copies figées :\n" + sortie.read_text(encoding="utf-8", errors="replace"))
            if time.time() > fin:
                self.fail("la question des copies figées n'est jamais apparue")
            time.sleep(0.05)
        return proc, sortie

    def terminer(self, proc, sortie):
        try:
            code = proc.wait(timeout=120)
        finally:
            proc.stdin.close()
        return code, sortie.read_text(encoding="utf-8", errors="replace")

    def interrompre_pendant_la_question(self, signal_envoye, attente=0):
        """Envoie le signal à tout le groupe, `attente` secondes après l'affichage de la question. Rend (code, sortie)."""
        proc, sortie = self.lancer_jusqu_a_la_question()
        time.sleep(attente)
        os.killpg(proc.pid, signal_envoye)
        return self.terminer(proc, sortie)

    def repondre_apres(self, attente):
        """Écrit « o » `attente` secondes après l'affichage de la question. Rend (code, sortie)."""
        proc, sortie = self.lancer_jusqu_a_la_question()
        time.sleep(attente)
        proc.stdin.write("o\n")
        proc.stdin.flush()
        return self.terminer(proc, sortie)

    @staticmethod
    def tuer(proc):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def verifie_comme_un_n(self, signal_envoye, nom, attente=0):
        code, texte = self.interrompre_pendant_la_question(signal_envoye, attente)
        self.assertEqual(code, 0, texte)                                              # le code de sortie du train est gardé
        for phrase in ("main poussé vers origin", RETARD, f"question interrompue ({nom})", "dossier d'exécution mis à jour", "terminé : main "):
            self.assertIn(phrase, texte)
        self.assertNotIn(PHRASE, texte)                                               # aucun rafraîchissement
        self.assertNotIn("interrompu (code", texte)                                   # le piège général n'a pas joué
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])        # aucune copie touchée
        self.assertEqual(sorted(p.name for p in self.dest.parent.glob("outils-figes.*")), [])   # aucun dossier de préparation
        self.assertTrue(self.marqueur.read_text(encoding="utf-8").startswith(self.t.main()))   # la note du retard est écrite
        self.assertEqual(sorted(p.name for p in self.t.data.glob("outils-figes-en-retard*")), ["outils-figes-en-retard"])   # écriture atomique : aucun temporaire
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists())        # le verrou est rendu
        self.assertEqual(self.t.git("rev-parse", "HEAD", cwd=self.t.run), self.t.main())   # le dossier d'exécution est à jour
        self.assertEqual(self.t.main(), self.t.origin_main())
        (rec,) = self.journal()                                                       # le journal des trains a sa ligne, code 0
        self.assertEqual((rec["code"], rec["sens"]), (0, "fusionne"))
        self.assertRegex(texte, r"===== fin du train : code 0 \(fusionné\)")

    def test_sigint_pendant_la_question_vaut_n(self):
        self.verifie_comme_un_n(signal.SIGINT, "INT")

    def test_sighup_pendant_la_question_vaut_n(self):
        self.verifie_comme_un_n(signal.SIGHUP, "HUP")

    def test_sigint_tardif_vaut_n(self):
        # R-20261110-08 : le signal arrive 2 s après l'affichage de la question (bien au-delà d'un pas de lecture d'une seconde) ; la question n'a pas expiré avant.
        self.verifie_comme_un_n(signal.SIGINT, "INT", attente=2)

    def test_reponse_lente_o_rafraichit_les_copies(self):
        # R-20261110-08 : la question attend la réponse sans délai ; un « o » écrit 2,5 s après l'affichage rafraîchit les copies (jamais un « n » par expiration).
        code, texte = self.repondre_apres(2.5)
        self.assertEqual(code, 0, texte)
        self.assertIn(PHRASE, texte)
        self.assertNotIn(RETARD, texte)
        self.assertNotIn("question interrompue", texte)
        self.assertEqual((self.dest / "copie" / "tools" / "dependance.py").read_text(encoding="utf-8"), "dependance v2\n")
        self.assertFalse(self.marqueur.exists())

    def test_lecture_du_script_les_pieges_generaux_sont_remis_apres_la_question(self):
        texte = (OUTILS / "finish_train.sh").read_text(encoding="utf-8")
        generaux = ("trap 'SIGCODE=INT; exit 130' INT", "trap 'SIGCODE=HUP; exit 129' HUP")
        for piege in generaux:
            self.assertEqual(len(re.findall(re.escape(piege), texte)), 2, piege)   # le piège général et sa remise, mot pour mot
        corps = texte[texte.index("frozen_ask() {"):]
        corps = corps[:corps.index("\n}\n")]
        self.assertLess(corps.index("trap 'FROZEN_SIG=INT' INT"), corps.index("read -r"))
        self.assertLess(corps.index("read -r"), corps.index("frozen_traps_generaux"))


if __name__ == "__main__":
    unittest.main()
