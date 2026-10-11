"""
Tests de tools/caption_diagnostic.py : classement, par cause, des légendes PDF que l'indexation ne retire pas du
texte de page ; la sortie ne contient que des comptes. Livre Markdown inventé, dans un dossier temporaire.

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/pmzilla_lab_library -v
"""
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import caption_diagnostic as diag  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402

TEXTE = "Un paragraphe de texte courant, assez long pour ressembler à une page de livre sur le flux de valeur. "


def bloc(numero: int, legende: str) -> str:
    return (f'<!-- figure id=fig-{numero:04d} source=pdf page={numero} image="x/fig-{numero:04d}.png" -->\n'
            f"Légende : {legende}\n")


def livre(*morceaux: str) -> str:
    return '---\ntitle: "Livre inventé"\nsource: "livre.pdf"\npages: 9\nfigures: 6\n---\n\n# Partie\n\n' + "\n".join(morceaux)


class Causes(unittest.TestCase):
    def cause(self, *morceaux: str) -> dict:
        _, corps = library.read_title(livre(*morceaux), "")
        return diag.diagnose(corps)

    def test_retiree(self):
        r = self.cause(TEXTE, "Figure 1.1 Un schéma inventé\n", bloc(1, "Figure 1.1 Un schéma inventé"))
        self.assertEqual((r["figures_pdf_avec_legende"], r["retirees"], dict(r["causes"])), (1, 1, {}))

    def test_collee_a_d_autres_mots(self):
        r = self.cause(TEXTE + "\nVoir Figure 1.2 Un schéma collé dans la phrase et la suite du texte.\n",
                       bloc(2, "Figure 1.2 Un schéma collé"))
        self.assertEqual(dict(r["causes"]), {"collée à d'autres mots": 1})

    def test_coupee_sur_plus_de_huit_lignes_ou_plusieurs_paragraphes(self):
        mots = "Figure 1.3 la légende très longue est répartie sur beaucoup de lignes de la page".split()
        sur_dix_lignes = "\n".join(mots[:10])
        r = self.cause(TEXTE, sur_dix_lignes + "\n", bloc(3, " ".join(mots[:10])))
        self.assertEqual(dict(r["causes"]), {"coupée sur plusieurs lignes ou paragraphes": 1})
        r = self.cause(TEXTE, "Figure 1.4 Début de la légende\n", "et la fin de la légende\n",
                       bloc(4, "Figure 1.4 Début de la légende et la fin de la légende"))
        self.assertEqual(dict(r["causes"]), {"coupée sur plusieurs lignes ou paragraphes": 1})

    def test_forme_differente(self):
        r = self.cause(TEXTE, "Figure 1.5 Un schema inventé de la coupe-\n", bloc(5, "Figure 1.5 Un schéma inventé de la coupe"))
        self.assertEqual(dict(r["causes"]), {"forme différente": 1})

    def test_trop_loin_apres_le_bloc_ou_au_dela_de_la_fenetre(self):
        r = self.cause(TEXTE, bloc(6, "Figure 1.6 Un schéma lointain"), "Figure 1.6 Un schéma lointain\n", TEXTE)
        self.assertEqual(dict(r["causes"]), {"trop loin du bloc": 1})
        paragraphes = [TEXTE + f"Variante {i}.\n" for i in range(library.CAPTION_LOOKBACK + 5)]
        r = self.cause("Figure 1.7 Un schéma très en amont\n", *paragraphes, bloc(7, "Figure 1.7 Un schéma très en amont"))
        self.assertEqual(dict(r["causes"]), {"trop loin du bloc": 1})

    def test_trop_loin_avant_la_figure_precedente(self):
        r = self.cause("Figure 1.8 Un schéma d'une page précédente\n", TEXTE,
                       bloc(8, "Figure 1.8 Autre légende présente"), TEXTE,
                       bloc(9, "Figure 1.8 Un schéma d'une page précédente"))
        self.assertEqual(r["causes"]["trop loin du bloc"], 1)

    def test_introuvable(self):
        r = self.cause(TEXTE, bloc(10, "Figure 1.9 Rien de tel dans la page"))
        self.assertEqual(dict(r["causes"]), {"introuvable": 1})

    def test_figures_epub_ou_sans_legende_ne_comptent_pas(self):
        r = self.cause(TEXTE, "<!-- figure id=fig-0001 source=epub -->\nLégende : Figure 1 Un schéma\n",
                       '<!-- figure id=fig-0002 source=pdf page=2 -->\nTexte alternatif : seulement une description\n')
        self.assertEqual((r["figures_pdf_avec_legende"], r["retirees"]), (0, 0))

    def test_comptes_additionnes(self):
        r = self.cause(TEXTE, "Figure 2.1 Un schéma inventé\n", bloc(1, "Figure 2.1 Un schéma inventé"),
                       TEXTE, bloc(2, "Figure 2.2 Rien de tel"), TEXTE,
                       "Voir Figure 2.3 Collée dans la phrase du texte.\n", bloc(3, "Figure 2.3 Collée"))
        self.assertEqual((r["figures_pdf_avec_legende"], r["retirees"]), (3, 1))
        self.assertEqual(dict(r["causes"]), {"introuvable": 1, "collée à d'autres mots": 1})


class Sortie(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def lancer(self, *arguments) -> tuple[str, int | None]:
        sortie, code = io.StringIO(), None
        with mock.patch.object(sys, "argv", ["caption_diagnostic.py", *arguments]), contextlib.redirect_stdout(sortie):
            try:
                diag.main()
            except SystemExit as erreur:
                code = erreur.code
        return sortie.getvalue(), code

    def test_la_sortie_ne_contient_que_des_comptes(self):
        chemin = self.tmp / "Titre secret du livre.md"
        chemin.write_text(livre(TEXTE, "Figure 3.1 Légende confidentielle\n", bloc(1, "Figure 3.1 Légende confidentielle"),
                                TEXTE, bloc(2, "Figure 3.2 Autre légende confidentielle")), encoding="utf-8")
        sortie, code = self.lancer(str(chemin))
        self.assertIsNone(code)
        self.assertEqual(sortie.splitlines()[:3], ["Figures PDF avec légende : 2", "Légendes retirées du texte de page : 1",
                                                    "Non retirées : 1"])
        for interdit in ("confidentielle", "Titre secret", "Livre inventé", "paragraphe de texte", str(self.tmp)):
            self.assertNotIn(interdit, sortie)
        self.assertIn("  introuvable : 1", sortie)
        self.assertEqual(chemin.read_text(encoding="utf-8").count("Figure 3.1"), 2)   # le livre n'est pas modifié

    def test_fichier_absent_et_arguments(self):
        sortie, code = self.lancer(str(self.tmp / "Titre secret.md"))
        self.assertEqual(code, "Fichier introuvable.")
        self.assertNotIn("Titre secret", sortie)
        self.assertEqual(self.lancer()[1], 1)


if __name__ == "__main__":
    unittest.main()
