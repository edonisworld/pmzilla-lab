"""
Tests de tools/sorting_exclusions.py (tableau des livres écartés par sort_by_domain.py) : cohérence de GARDES avec le
vrai MAPPING (lu dans le texte source, aucun livre n'est lu) et lecture seule sur de faux fichiers.

    python3 -m unittest discover -s tests/sort_by_domain -v
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import sorting_exclusions as ecartes  # noqa: E402
import mapping_lab  # noqa: E402


class GardesEtMapping(unittest.TestCase):
    def test_tous_les_ecartes_sont_dans_gardes_et_inversement(self):
        ecartes_reels = {k for k, codes in mapping_lab.MAPPING.items() if not codes}
        self.assertEqual(ecartes_reels, set(ecartes.GARDES))

    def test_chaque_livre_garde_existe_et_est_copie(self):
        for ecarte, garde in ecartes.GARDES.items():
            if garde is not None:
                self.assertTrue(mapping_lab.MAPPING.get(garde), f"{ecarte} -> {garde} : écarté ou absent de MAPPING")

    def test_chaque_ecarte_a_un_commentaire(self):
        source = (Path(__file__).resolve().parents[2] / "tools" / "mapping_lab.py").read_text(encoding="utf-8")
        commentaires = ecartes.comments(source)
        for cle in ecartes.GARDES:
            self.assertTrue(commentaires.get(cle), cle)


class Tableau(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.mapping = {"R/a-fr.md": "", "R/a-en.md": "OD", "R/b-hors-sujet.md": "", "R/c-fr.md": "", "R/c-en.md": "P"}
        self.gardes = {"R/a-fr.md": "R/a-en.md", "R/b-hors-sujet.md": None}   # « c-fr » : pas dans GARDES
        self.commentaires = {"R/a-fr.md": "doublon FR : on garde l'original", "R/b-hors-sujet.md": "écarté : hors sujet"}
        self.ecrire("R/a-fr.md", '---\ntitle: "A"\nsource: "a-fr.pdf"\nfigures: 3\n---\n\n' + "x" * 2048)
        self.ecrire("R/a-en.md", '---\ntitle: "A"\nsource: "a-en.epub"\nfigures: 12\n---\n\n' + "x" * 10240)
        self.ecrire("R/b-hors-sujet.md", "Sans en-tête\n")

    def ecrire(self, relatif: str, texte: str) -> None:
        chemin = self.tmp / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")

    def tableau(self) -> str:
        return ecartes.table(self.tmp, self.mapping, self.gardes, self.commentaires)

    def test_lignes_taille_format_et_figures(self):
        sortie = self.tableau()
        self.assertIn("3 livres écartés par sort_by_domain.py : 1 doublons, 1 écartés sans doublon (hors sujet, version concise), 1 à identifier.", sortie.split("\n")[0])
        self.assertIn("| R/a-fr.md | R/a-en.md (OD) | doublon FR : on garde l'original | 2 Ko / 10 Ko | PDF / EPUB | 3 / 12 |", sortie)
        self.assertIn("| R/b-hors-sujet.md | aucun (écarté, pas un doublon) | écarté : hors sujet | 0 Ko / — | ? / — | ? / — |", sortie)
        self.assertIn("| R/c-fr.md | à identifier | (aucun commentaire) | absent / — | absent / — | absent / — |", sortie)

    def test_lecture_seule(self):
        avant = {p: p.read_bytes() for p in self.tmp.rglob("*") if p.is_file()}
        self.tableau()
        self.assertEqual({p: p.read_bytes() for p in self.tmp.rglob("*") if p.is_file()}, avant)
        self.assertEqual(sorted(p.name for p in self.tmp.rglob("*") if p.is_file()),
                         ["a-en.md", "a-fr.md", "b-hors-sujet.md"])

    def test_garde_absent_du_disque(self):
        (self.tmp / "R" / "a-en.md").unlink()
        self.assertIn("2 Ko / absent | PDF / absent | 3 / absent", self.tableau())


if __name__ == "__main__":
    unittest.main()
