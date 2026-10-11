"""
Tests de tools/sauvegarde_sanctum.sh : copie datée, refus d'écraser, rotation, sauvegarde du 2026-10-07 conservée.

    uv run python -m unittest discover -s tests/sauvegarde_sanctum -v

Faux sanctum et faux dossier de sauvegardes dans un dossier temporaire (variables SANCTUM_SOURCE, SANCTUM_SAUVEGARDES,
SANCTUM_DATE) : le vrai sanctum n'est jamais lu ni copié.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "sauvegarde_sanctum.sh"
SECRET = "contenu-du-vecu-a-ne-jamais-afficher"


class Sauvegarde(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.source = base / "memory"
        (self.source / "pmzilla-delivery-bmad" / "sessions").mkdir(parents=True)
        (self.source / "pmzilla-delivery-bmad" / "MEMORY.md").write_text(SECRET, encoding="utf-8")
        (self.source / "pmzilla-delivery-bmad" / "sessions" / "s.md").write_text(SECRET, encoding="utf-8")
        (self.source / "pmzilla-scaling-bmad").mkdir()
        (self.source / "pmzilla-scaling-bmad" / "MEMORY.md").write_text(SECRET, encoding="utf-8")
        self.dest = base / "sauvegardes"

    def tearDown(self):
        self.temp.cleanup()

    def lancer(self, date: str, garder: str = "6", source: Path | None = None):
        env = {**os.environ, "SANCTUM_SOURCE": str(source or self.source), "SANCTUM_SAUVEGARDES": str(self.dest),
               "SANCTUM_DATE": date, "SANCTUM_GARDER": garder}
        return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)

    def dossiers(self) -> list[str]:
        return sorted(p.name for p in self.dest.iterdir()) if self.dest.exists() else []

    def test_copie_datee_avec_le_nombre_de_fichiers(self):
        fait = self.lancer("2026-11-01")
        self.assertEqual(fait.returncode, 0, fait.stderr)
        self.assertIn("bmad-memory-2026-11-01 (3 fichiers)", fait.stdout)
        copie = self.dest / "bmad-memory-2026-11-01"
        self.assertEqual((copie / "pmzilla-delivery-bmad" / "MEMORY.md").read_text(encoding="utf-8"), SECRET)
        self.assertTrue((copie / "pmzilla-delivery-bmad" / "sessions" / "s.md").is_file())

    def test_n_affiche_jamais_le_contenu(self):
        fait = self.lancer("2026-11-01")
        self.assertNotIn(SECRET, fait.stdout + fait.stderr)

    def test_refuse_d_ecraser_la_sauvegarde_du_jour(self):
        self.lancer("2026-11-01")
        (self.source / "pmzilla-scaling-bmad" / "MEMORY.md").write_text("nouveau", encoding="utf-8")
        fait = self.lancer("2026-11-01")
        self.assertEqual(fait.returncode, 1)
        self.assertIn("La sauvegarde du jour existe déjà", fait.stdout)
        copie = self.dest / "bmad-memory-2026-11-01" / "pmzilla-scaling-bmad" / "MEMORY.md"
        self.assertEqual(copie.read_text(encoding="utf-8"), SECRET)       # l'ancienne copie est intacte

    def test_rotation_garde_les_plus_recentes_et_affiche_ce_qu_elle_supprime(self):
        for jour in range(1, 9):                                           # 8 sauvegardes, 6 gardées
            fait = self.lancer(f"2026-11-0{jour}")
            self.assertEqual(fait.returncode, 0, fait.stderr)
        self.assertEqual(self.dossiers(), [f"bmad-memory-2026-11-0{j}" for j in range(3, 9)])
        self.assertIn("Supprimée : ", fait.stdout)

    def test_la_sortie_nomme_ce_qui_est_supprime(self):
        for jour in range(1, 7):
            self.lancer(f"2026-11-0{jour}")
        fait = self.lancer("2026-11-07")
        self.assertIn(f"Supprimée : {self.dest}/bmad-memory-2026-11-01 (3 fichiers)", fait.stdout)
        self.assertEqual(fait.stdout.count("Supprimée"), 1)             # une seule : les 6 plus récentes restent

    def test_la_sauvegarde_du_2026_10_07_n_est_jamais_supprimee(self):
        ancienne = self.dest / "bmad-memory-2026-10-07"
        (ancienne / "pmzilla-delivery-bmad").mkdir(parents=True)
        (ancienne / "pmzilla-delivery-bmad" / "MEMORY.md").write_text("ancien", encoding="utf-8")
        for jour in range(1, 9):
            self.lancer(f"2026-11-0{jour}")
        self.assertIn("bmad-memory-2026-10-07", self.dossiers())
        self.assertEqual((ancienne / "pmzilla-delivery-bmad" / "MEMORY.md").read_text(encoding="utf-8"), "ancien")
        # la protégée s'ajoute aux 6 plus récentes (elle est la plus ancienne : sans protection, elle serait supprimée)
        self.assertEqual(self.dossiers(), ["bmad-memory-2026-10-07"] + [f"bmad-memory-2026-11-0{j}" for j in range(3, 9)])

    def test_les_autres_dossiers_du_dossier_des_sauvegardes_ne_sont_pas_touches(self):
        autre = self.dest / "autre-chose"
        autre.mkdir(parents=True)
        (autre / "f.txt").write_text("x", encoding="utf-8")
        for jour in range(1, 9):
            self.lancer(f"2026-11-0{jour}")
        self.assertTrue((autre / "f.txt").is_file())

    def test_source_absente_ou_vide(self):
        fait = self.lancer("2026-11-01", source=Path(self.temp.name) / "absent")
        self.assertEqual(fait.returncode, 2)
        self.assertIn("Sanctum introuvable ou vide", fait.stdout)
        self.assertEqual(self.dossiers(), [])

    def test_date_invalide(self):
        fait = self.lancer("hier")
        self.assertEqual(fait.returncode, 2)
        self.assertEqual(self.dossiers(), [])

    def test_deuxieme_sauvegarde_du_meme_jour_avec_une_etiquette(self):
        self.lancer("2026-11-01")
        fait = self.lancer("2026-11-01-lot6")
        self.assertEqual(fait.returncode, 0, fait.stderr)
        self.assertEqual(self.dossiers(), ["bmad-memory-2026-11-01", "bmad-memory-2026-11-01-lot6"])
        self.assertEqual(self.lancer("2026-11-01-lot6").returncode, 1)        # jamais d'écrasement non plus

    def test_une_sauvegarde_etiquetee_n_est_ni_comptee_ni_supprimee_par_la_rotation(self):
        self.lancer("2026-11-01-lot6")
        for jour in ("2026-11-02", "2026-11-03", "2026-11-04"):
            self.lancer(jour, garder="2")
        self.assertEqual(self.dossiers(), ["bmad-memory-2026-11-01-lot6", "bmad-memory-2026-11-03", "bmad-memory-2026-11-04"])

    def test_etiquette_invalide(self):
        for date in ("2026-11-01-", "2026-11-01-A B", "2026-11-01-../x"):
            self.assertEqual(self.lancer(date).returncode, 2, date)
        self.assertEqual(self.dossiers(), [])


if __name__ == "__main__":
    unittest.main()
