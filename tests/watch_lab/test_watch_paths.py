"""Tests de tools/watch_paths.py : nom actuel (création si absent) ; un dossier resté à l'ancien nom est refusé.

Tout se passe dans des dossiers temporaires vides : on ne lit jamais Veille-Lab, Watch-Lab ni leurs contenus.
"""
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import watch_paths  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.ws, True)

    def appeler(self, fonction, *args):
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur):
            resultat = fonction(*args)
        return resultat, erreur.getvalue()


class Dossiers(Base):
    def test_aucun_dossier_le_nouveau_nom_sans_avertissement(self):
        for fonction, nom in ((watch_paths.config_dir, "watch"), (watch_paths.lab_dir, "Watch-Lab"),
                              (watch_paths.excluded_dir, "Watch-Excluded")):
            chemin, erreur = self.appeler(fonction, self.ws)
            self.assertEqual((chemin, erreur), (self.ws / nom, ""))

    def test_ancien_dossier_seul_refuse_avec_le_nom_actuel_et_l_outil_de_migration(self):
        for fonction, ancien, nouveau in ((watch_paths.config_dir, "veille", "watch"),
                                          (watch_paths.lab_dir, "Veille-Lab", "Watch-Lab"),
                                          (watch_paths.excluded_dir, "Veille-Ecartes", "Watch-Excluded")):
            (self.ws / ancien).mkdir()
            with self.assertRaises(SystemExit) as refus:
                fonction(self.ws)
            message = str(refus.exception)
            self.assertIn(f"{ancien}/", message)
            self.assertIn(f"{nouveau}/", message)
            self.assertIn("tools/migrate_watch.py", message)

    def test_le_nouveau_a_priorite_quand_les_deux_existent(self):
        for nom in ("veille", "watch"):
            (self.ws / nom).mkdir()
        chemin, erreur = self.appeler(watch_paths.config_dir, self.ws)
        self.assertEqual((chemin, erreur), (self.ws / "watch", ""))

    def test_un_fichier_du_meme_nom_n_est_pas_un_dossier(self):
        (self.ws / "watch").write_text("x")
        self.assertEqual(self.appeler(watch_paths.config_dir, self.ws)[0], self.ws / "watch")


class Collection(Base):
    def test_sous_dossier_de_collection(self):
        lab = self.ws / "Watch-Lab"
        lab.mkdir()
        self.assertEqual(self.appeler(watch_paths.collection_name, lab), ("watch", ""))
        (lab / "veille").mkdir()                          # reste d'une migration interrompue : refusé
        with self.assertRaises(SystemExit) as refus:
            watch_paths.collection_name(lab)
        self.assertIn("Watch-Lab/watch/", str(refus.exception))
        self.assertIn("tools/migrate_watch.py", str(refus.exception))
        (lab / "watch").mkdir()
        self.assertEqual(self.appeler(watch_paths.collection_name, lab)[0], "watch")

    def test_dossier_vide(self):
        self.assertEqual(self.appeler(watch_paths.collection_name, self.ws / "Watch-Lab")[0], "watch")

    def test_liste_a_lire_seulement_le_nouveau_nom(self):
        self.assertEqual(watch_paths.to_read_name(self.ws / "Watch-Lab"), "_to-read.md")
        self.assertEqual(watch_paths.to_read_name(self.ws / "Veille-Lab"), "_to-read.md")


class LigneDeCommande(Base):
    def lancer(self, *args):
        return subprocess.run([sys.executable, str(TOOLS / "watch_paths.py"), *args], capture_output=True, text=True)

    def test_chemins_ecrits_pour_watch_sh(self):
        self.assertEqual(self.lancer("lab", str(self.ws)).stdout.strip(), str(self.ws / "Watch-Lab"))
        self.assertEqual(self.lancer("excluded", str(self.ws)).stdout.strip(), str(self.ws / "Watch-Excluded"))
        self.assertEqual(self.lancer("collection", str(self.ws)).stdout.strip(), "watch")

    def test_ancien_dossier_seul_code_de_sortie_non_nul_et_message(self):
        (self.ws / "Veille-Lab").mkdir()
        resultat = self.lancer("lab", str(self.ws))
        self.assertNotEqual(resultat.returncode, 0)
        self.assertEqual(resultat.stdout, "")
        self.assertIn("Watch-Lab/", resultat.stderr)
        self.assertIn("tools/migrate_watch.py", resultat.stderr)

    def test_usage(self):
        self.assertEqual(self.lancer("inconnu", str(self.ws)).returncode, 2)

    def test_aucune_dependance_hors_bibliotheque_standard(self):
        source = (TOOLS / "watch_paths.py").read_text(encoding="utf-8")
        imports = {l.split()[1].split(".")[0] for l in source.splitlines() if l.startswith(("import ", "from "))}
        self.assertEqual(imports - {"__future__", "os", "sys", "pathlib", "lab_paths"}, set())


if __name__ == "__main__":
    unittest.main()
