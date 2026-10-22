"""Garde du dépôt réel (change pre-commit-secret-scan, design D6) : aucun fichier suivi ne contient de secret non déclaré.

Chaque fichier suivi (`git ls-files`, lu dans l'arbre de travail) est passé à tools/secret_scan.py, binaires (octet nul) ignorés. Un échec
nomme `fichier:ligne (famille)`, jamais la valeur. Une trouvaille dont le chemin et l'empreinte sont dans tools/secret_scan_exemples.txt passe.

    uv run python -W ignore -m unittest discover -s tests/secret_scan -q -f
"""
import subprocess
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import secret_scan  # noqa: E402


def fichiers_suivis():
    sortie = subprocess.run(["git", "ls-files", "-z"], cwd=RACINE, capture_output=True, check=True).stdout
    return [f for f in sortie.decode().split("\0") if f]


class DepotReel(unittest.TestCase):
    def test_aucun_fichier_suivi_ne_contient_de_secret_non_declare(self):
        declares = secret_scan.load_declared(str(RACINE / secret_scan.LISTE_EXEMPLES))
        constats = []
        for chemin in fichiers_suivis():
            fichier = RACINE / chemin
            if not fichier.is_file():   # supprimé de l'arbre de travail ou lien rompu : rien à lire
                continue
            octets = fichier.read_bytes()
            if b"\0" in octets:
                continue
            refusees, _ = secret_scan.check(chemin, octets.decode("utf-8", errors="ignore"), declares)
            constats += [f"secret possible dans le dépôt : {chemin}:{t.line} ({secret_scan.label(t.family)})" for t in refusees]
        if constats:
            self.fail("\n".join(constats))


if __name__ == "__main__":
    unittest.main()
