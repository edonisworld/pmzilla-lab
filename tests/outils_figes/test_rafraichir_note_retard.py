"""R-20261110-03, -04 : un rafraîchissement réussi (code 0) de tools/outils_figes/rafraichir.sh retire la note `outils-figes-en-retard` voisine du dossier des outils
figés ; un échec (liste ou dossiers.conf manquant, code 4) la laisse. Remplace : rien. Retrait : avec le bac à sable.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "tools" / "outils_figes"


class NoteDuRetard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.dest = self.base / "outils-figes"
        self.dest.mkdir()
        self.note = self.base / "outils-figes-en-retard"
        self.note.write_text("a" * 40 + " cd /x && bash tools/outils_figes/rafraichir.sh /x /y\n", encoding="utf-8")
        (self.dest / "dossiers.conf").write_text("".join(f"{cle}={self.base / dossier}\n" for cle, dossier in
                                                         (("maison", "maison"), ("workspace", "workspace"), ("worktrees", "worktrees"),
                                                          ("etapes", "etapes"), ("scratchpad", "sessions"), ("donnees", "donnees"),
                                                          ("noms", "noms.txt"), ("crochets", "crochets"), ("cache_uv", "cache-uv"))) +
                                                 f"python={sys.executable}\n", encoding="utf-8")

    def image(self):
        """Une image des fichiers de la liste, sans .git (comme le dossier de préparation d'un train) : les contrôles Git de R-20261110-06 n'y valent pas."""
        depot = self.base / "image"
        liste = SOURCE / "liste.txt"
        (depot / "tools" / "outils_figes").mkdir(parents=True, exist_ok=True)
        (depot / "tools" / "outils_figes" / "liste.txt").write_bytes(liste.read_bytes())
        for ligne in liste.read_text(encoding="utf-8").splitlines():
            if ligne.strip() and not ligne.startswith("#"):
                genre, chemin = ligne.split(" ", 1)
                source = SOURCE / chemin if genre == "E" else RACINE / chemin
                cible = depot / "tools" / "outils_figes" / chemin if genre == "E" else depot / chemin
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_bytes(source.read_bytes())
        return depot

    def lancer(self, depot=None):
        depot = depot or self.image()
        return subprocess.run(["/bin/bash", str(SOURCE / "rafraichir.sh"), str(depot), str(self.dest), "--extrait-du-train"], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin"})

    def test_un_rafraichissement_reussi_retire_la_note(self):
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.note.exists())

    def test_un_rafraichissement_reussi_sans_note_reste_reussi(self):
        self.note.unlink()
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_un_echec_garde_la_note(self):
        vide = self.base / "depot-vide"
        vide.mkdir()
        r = self.lancer(vide)                                   # liste introuvable : code 4
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertTrue(self.note.exists())

    def test_dossiers_conf_absent_garde_la_note(self):
        (self.dest / "dossiers.conf").unlink()
        r = self.lancer()
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertTrue(self.note.exists())


if __name__ == "__main__":
    unittest.main()
