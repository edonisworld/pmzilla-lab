"""Garde statique (test-speed, R-139) : un faux serveur de test lancé par serve_forever() sans poll_interval sonde toutes les 0,5 s par défaut,
et son shutdown() attend jusqu'à un tour de sondage : 0,5 s perdues par test. Chaque ligne d'un fichier sous tests/ qui écrit
serve_forever doit donc aussi écrire poll_interval."""
import unittest
from pathlib import Path

RACINE_TESTS = Path(__file__).resolve().parent.parent
MOT = "serve_" + "forever"   # coupé pour que ce fichier ne se cite pas lui-même


def lignes_fautives(racine):
    fautives = []
    for fichier in sorted(racine.rglob("*.py")):
        if fichier == Path(__file__).resolve() or "__pycache__" in fichier.parts:
            continue
        for numero, ligne in enumerate(fichier.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if MOT in ligne and "poll_interval" not in ligne:
                fautives.append(f"{fichier.relative_to(racine.parent)}:{numero}")
    return fautives


class SondageDesFauxServeurs(unittest.TestCase):
    def test_aucun_faux_serveur_au_sondage_par_defaut(self):
        self.assertEqual(lignes_fautives(RACINE_TESTS), [], "ajouter poll_interval=0.01 à ces appels")

    def test_la_garde_voit_un_appel_sans_poll_interval(self):
        import tempfile
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier) / "tests"
            (racine / "x").mkdir(parents=True)
            (racine / "x" / "aide.py").write_text(f"t = Thread(target=s.{MOT}, daemon=True)\n"
                                                  f"u = Thread(target=s.{MOT}, kwargs={{'poll_interval': 0.01}})\n")
            self.assertEqual(lignes_fautives(racine), ["tests/x/aide.py:1"])


if __name__ == "__main__":
    unittest.main()
