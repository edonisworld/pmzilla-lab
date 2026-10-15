"""
Décompte des articles retenus par le passage du jour (change morning-summary, R-50, design D3, tâche 3.1).

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/watch_triage -v

La liste à lire classée (`watch_triage.py digest`) écrit `veille-retenus.json` dans le dossier de données : la date du passage et le
nombre d'articles collectés ce jour-là sans raison d'écart, mode observation compris. Aucun titre, lien, source ni chemin. La liste
simple (`watch_lab.py digest`) n'écrit rien. Un dossier non inscriptible ne fait pas échouer la liste à lire.
Tout est dans un dossier temporaire et le faux magasin de la classe Base voisine : aucun dossier réel, aucun réseau.
"""
import argparse
import contextlib
import io
import json
import os
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import watch_triage as tri  # noqa: E402
import watch_lab as veille  # noqa: E402
import test_watch_triage as voisin  # noqa: E402

JOUR = "2026-10-14"
SENTINELLE = "SENTINELLE-TITRE-XYZ"


class Retenus(voisin.Base):
    def setUp(self):
        super().setUp()
        self.donnees = self.tmp / "donnees"
        self.donnees.mkdir()
        self.fichier = self.donnees / "veille-retenus.json"
        env = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.donnees), "PMZILLA_LAB_TODAY": JOUR})
        env.start()
        self.addCleanup(env.stop)

    def liste(self):
        return self.lancer(tri.cmd_digest)

    def test_trois_retenus_sur_cinq_du_jour(self):
        self.ajouter("a1.md", 5, collecte=JOUR)
        self.ajouter("a2.md", 4, collecte=JOUR)
        self.ajouter("a3.md", 4, collecte=JOUR)
        self.ajouter("a4.md", 4, promo=1, collecte=JOUR)
        self.ajouter("a5.md", 4, compilation=1, collecte=JOUR)
        self.liste()
        self.assertEqual(json.loads(self.fichier.read_text(encoding="utf-8")), {"date": JOUR, "retained": 3})

    def test_les_articles_d_un_autre_jour_ne_comptent_pas(self):
        self.ajouter("a1.md", 5, collecte=JOUR)
        self.ajouter("a2.md", 5, collecte="2026-10-13")
        self.liste()
        self.assertEqual(json.loads(self.fichier.read_text(encoding="utf-8"))["retained"], 1)

    def test_aucun_article_du_jour_ecrit_zero(self):
        self.ajouter("a1.md", 5, collecte="2026-10-13")
        self.liste()
        self.assertEqual(json.loads(self.fichier.read_text(encoding="utf-8")), {"date": JOUR, "retained": 0})

    def test_mode_observation_compris(self):
        self.ajouter("a1.md", 5, collecte=JOUR)
        self.ajouter("a2.md", 0, collecte=JOUR)     # le filtre l'écarterait : il ne compte pas
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tri.config()["mode"], "observation")
        self.liste()
        self.assertEqual(json.loads(self.fichier.read_text(encoding="utf-8"))["retained"], 1)

    def test_ni_titre_ni_lien_ni_source_ni_chemin(self):
        self.ajouter("a1.md", 5, titre=SENTINELLE, source="source-secrete.test", collecte=JOUR)
        self.liste()
        texte = self.fichier.read_text(encoding="utf-8")
        for interdit in (SENTINELLE, "source-secrete", "http", "a1.md", str(self.tmp)):
            self.assertNotIn(interdit, texte)
        self.assertEqual(set(json.loads(texte)), {"date", "retained"})

    def test_droits_du_proprietaire_seul_et_aucun_temporaire(self):
        self.ajouter("a1.md", 5, collecte=JOUR)
        self.liste()
        self.assertEqual(stat.S_IMODE(self.fichier.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in self.donnees.iterdir()], ["veille-retenus.json"])

    def test_le_passage_suivant_remplace_le_fichier(self):
        self.ajouter("a1.md", 5, collecte=JOUR)
        self.liste()
        self.ajouter("a2.md", 5, collecte=JOUR)
        self.liste()
        self.assertEqual(json.loads(self.fichier.read_text(encoding="utf-8"))["retained"], 2)

    def test_la_liste_simple_n_ecrit_rien(self):
        self.ajouter("a1.md", 5, collecte=JOUR)
        self.fichier.write_text('{"date": "2026-10-01", "retained": 9}', encoding="utf-8")
        avant = self.fichier.read_text(encoding="utf-8")
        with mock.patch.object(veille, "open_store", return_value=self.watch), contextlib.redirect_stdout(io.StringIO()):
            veille.cmd_digest(argparse.Namespace(days=7))
        self.assertEqual(self.fichier.read_text(encoding="utf-8"), avant)

    def test_dossier_non_inscriptible_la_liste_est_ecrite_et_le_dit(self):
        self.ajouter("a1.md", 5, collecte=JOUR)
        self.donnees.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(self.donnees.chmod, 0o700)
        if os.access(self.donnees, os.W_OK):
            self.skipTest("l'utilisateur du test écrit malgré les droits (administrateur)")
        sortie = self.liste()
        self.assertTrue(veille.to_read_file().exists())
        self.assertIn("Décompte des articles retenus non enregistré", sortie)
        self.assertFalse(self.fichier.exists())

    def test_dossier_de_donnees_absent_la_liste_est_ecrite(self):
        self.ajouter("a1.md", 5, collecte=JOUR)
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.tmp / "absent" / "profond")}):
            sortie = self.liste()
        self.assertTrue(veille.to_read_file().exists())
        self.assertTrue((self.tmp / "absent" / "profond" / "veille-retenus.json").exists() or "non enregistré" in sortie)


if __name__ == "__main__":
    unittest.main()
