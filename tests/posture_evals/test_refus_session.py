"""
Refus du jeu d'essai dans une session Claude Code (dossier de décision 2026-10-26-droits-session-push-runner, décision 5).

    bash tests/run_all.sh posture_evals

Le jeu d'essai est payant et reste à l'auteur : tools/posture_evals.py lancé comme script avec le marqueur de session posé (même vide)
sort avec le code 6 avant toute lecture du lab, toute copie et tout appel. Le test lance le script dans un sous-processus avec un faux
`claude` en tête du PATH qui note ses appels : aucun appel, aucun coût, aucune base. Sans marqueur, `--help` n'est pas refusé (la garde ne
vise que le lancement du script avec le marqueur) ; l'import du module par les autres suites n'est pas visé.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "posture_evals.py"
MARQUEUR = "CLAUDECODE"


class RefusEnSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.appels = Path(self.tmp.name) / "appels"
        faux = self.bin / "claude"
        faux.write_text(f'#!/bin/sh\necho "claude: $*" >> "{self.appels}"\nexit 0\n', encoding="utf-8")
        faux.chmod(0o755)

    def lance(self, *arguments, marqueur=None):
        environnement = {k: v for k, v in os.environ.items() if k != MARQUEUR}
        environnement["PATH"] = f"{self.bin}{os.pathsep}{environnement.get('PATH', '')}"
        if marqueur is not None:
            environnement[MARQUEUR] = marqueur
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *arguments], capture_output=True, text=True, env=environnement, timeout=120)

    def test_session_refus_code_6_message_clair_rien_lance(self):
        resultat = self.lance(marqueur="1")
        self.assertEqual(resultat.returncode, 6, resultat.stderr)
        self.assertIn("payant, réservé à l'auteur", resultat.stderr)
        self.assertIn("Rien n'a été lancé", resultat.stderr)
        self.assertFalse(self.appels.exists(), "aucun appel payant ne doit partir")

    def test_session_marqueur_vide_refuse_aussi(self):
        resultat = self.lance(marqueur="")
        self.assertEqual(resultat.returncode, 6, resultat.stderr)
        self.assertFalse(self.appels.exists())

    def test_session_toutes_les_options_sont_refusees(self):
        for options in (["--help"], ["--committed-state"], ["--prerequisites-only"], ["--cases", "c1"], ["--branch", "main"]):
            with self.subTest(options=options):
                resultat = self.lance(*options, marqueur="1")
                self.assertEqual(resultat.returncode, 6, resultat.stderr)
                self.assertFalse(self.appels.exists())

    def test_hors_session_la_garde_ne_refuse_pas(self):
        resultat = self.lance("--help")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertNotIn("réservé à l'auteur", resultat.stderr)
        self.assertFalse(self.appels.exists())


if __name__ == "__main__":
    unittest.main()
