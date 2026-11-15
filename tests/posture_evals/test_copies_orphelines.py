"""
Copies de séance orphelines du jeu d'essai (tools/posture_evals.py, idée #402) : SIGTERM et SIGHUP suivent le chemin de Ctrl-C, les
worktrees laissés sous le dossier des essais sont listés au démarrage d'un passage et retirés seulement avec --remove-orphans.

    bash tests/run_all.sh posture_evals

Dépôts Git créés par les tests dans un dossier temporaire : jamais les vrais worktrees, aucun appel à Claude.
"""
import contextlib
import io
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import posture_evals as essai  # noqa: E402


def git(dossier, *args):
    return subprocess.run(["git", "-C", str(dossier), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          capture_output=True, text=True, check=True).stdout


class SignauxEtCopies(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orphelines."))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.depot = self.tmp / "depot"
        self.depot.mkdir()
        git(self.depot, "init", "-q", "-b", "main")
        (self.depot / "a.txt").write_text("a", encoding="utf-8")
        git(self.depot, "add", "a.txt")
        git(self.depot, "commit", "-q", "-m", "init")
        self.data = self.tmp / "essais"
        self.data.mkdir()
        for patch in (mock.patch.object(essai, "WORKSPACE", self.depot), mock.patch.object(essai, "DATA", self.data)):
            patch.start()
            self.addCleanup(patch.stop)

    def copie(self, dossier: Path) -> Path:
        dossier.parent.mkdir(parents=True, exist_ok=True)
        git(self.depot, "worktree", "add", "-q", "--detach", str(dossier), "main")
        return dossier

    def liste(self) -> list[str]:
        return [Path(p).resolve().as_posix() for p in
                (line[9:] for line in git(self.depot, "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree "))]

    def lancer_orphelines(self, retirer: bool) -> str:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            essai.handle_orphans(self.data, retirer)
        return sortie.getvalue()

    def test_une_copie_orpheline_est_listee_et_pas_retiree_sans_l_option(self):
        orpheline = self.copie(self.data / "2026-10-07-224033" / "copie-cas")
        sortie = self.lancer_orphelines(False)
        self.assertIn("copie-cas", sortie)
        self.assertIn("--remove-orphans", sortie)
        self.assertTrue(orpheline.is_dir())
        self.assertIn(orpheline.resolve().as_posix(), self.liste())

    def test_l_option_retire_la_copie_orpheline(self):
        orpheline = self.copie(self.data / "2026-10-07-224033" / "copie-cas")
        self.assertIn("retirée", self.lancer_orphelines(True))
        self.assertFalse(orpheline.exists())
        self.assertNotIn(orpheline.resolve().as_posix(), self.liste())

    def test_un_worktree_hors_du_dossier_des_essais_n_est_jamais_liste_ni_touche(self):
        dehors = self.copie(self.tmp / "ailleurs" / "wt-feature")
        voisin = self.copie(self.tmp / "essais-voisin" / "copie-cas")   # préfixe de nom proche, hors du dossier
        orpheline = self.copie(self.data / "2026-10-09-184754" / "copie-autre")
        sortie = self.lancer_orphelines(True)
        self.assertNotIn("wt-feature", sortie)
        self.assertNotIn("essais-voisin", sortie)
        self.assertTrue(dehors.is_dir() and voisin.is_dir())
        self.assertFalse(orpheline.exists())
        self.assertEqual(essai.trial_orphans(self.data), [])

    def test_aucune_copie_aucune_ligne(self):
        self.assertEqual(self.lancer_orphelines(True), "")

    def test_le_depot_principal_n_est_jamais_une_orpheline_meme_sous_le_dossier_des_essais(self):
        self.assertEqual(essai.trial_orphans(self.depot.parent), [])   # le dossier des essais contient le dépôt : il est exclu par construction
        self.assertTrue(self.depot.is_dir())

    def test_sigterm_et_sighup_passent_par_le_finally_et_retirent_la_copie(self):
        for nom in ("SIGTERM", "SIGHUP"):
            with self.subTest(signal=nom):
                avant = {n: signal.getsignal(getattr(signal, n)) for n in ("SIGTERM", "SIGHUP")}
                self.addCleanup(lambda avant=avant: [signal.signal(getattr(signal, n), h) for n, h in avant.items()])
                essai.install_signal_exit()
                copie = self.copie(self.data / "2026-10-10-100000" / f"copie-{nom}")
                with self.assertRaises(KeyboardInterrupt):
                    try:
                        os.kill(os.getpid(), getattr(signal, nom))
                        signal.pause()
                    finally:
                        essai.drop_copy(copie)
                self.assertFalse(copie.exists())
                self.assertEqual(essai.trial_orphans(self.data), [])

    def test_l_option_existe_dans_le_parseur_du_passage(self):
        with mock.patch.object(sys, "argv", ["posture_evals.py", "--remove-orphans", "--prerequisites-only"]), \
             mock.patch.object(essai, "check_prerequisites_only", return_value=0), \
             mock.patch.object(essai, "CASES_FILE", self.tmp / "inexistant.yaml"):
            with self.assertRaises(SystemExit) as erreur:
                essai.main()
        self.assertIn("Cas introuvables", str(erreur.exception))   # l'option est acceptée : l'arrêt vient du fichier de cas


if __name__ == "__main__":
    unittest.main()
