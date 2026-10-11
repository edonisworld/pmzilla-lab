"""
Tests de `convert_books.py --figure-statistics` (étape 0 de la piste « Illustrations et schémas ») sur un EPUB
et des PDF minuscules fabriqués par le test : figures avec et sans figcaption, légende « Figure 1.2 » dans le
paragraphe suivant, texte alternatif vide et rempli, image intégrée, dessin vectoriel, ornement, page scannée.

    uv run --with pymupdf4llm --with ebooklib --with markdownify --with beautifulsoup4 \
        python -m unittest discover -s tests/convert_books -v

L'analyse ne lit que des livres inventés, dans un dossier temporaire ; on vérifie qu'elle ne modifie aucun livre,
n'écrit que _statistiques_figures.txt (jamais de Markdown) et que l'agrégat, dernière partie de la sortie, ne
contient aucun titre de livre.
"""
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_books as cb  # noqa: E402
import test_convert_books as base  # noqa: E402  (fabrique d'EPUB et de PDF)

RACINE = Path(__file__).resolve().parents[2]

CHAPITRE_FIGURES = """
<h1>Chapitre un</h1>
<figure><img src="a.png" alt="Trois colonnes d'un tableau kanban"/><figcaption>Figure 1.1 Un tableau kanban</figcaption></figure>
<figure><img src="b.png" alt=""/></figure>
<p><img src="c.png" alt="Courbe du lead time"/></p>
<p>Figure 1.2 La courbe du lead time</p>
<p><img src="d.png" alt=""/></p>
<p>Un paragraphe ordinaire qui commente le schéma sans en être la légende.</p>
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><title>Cycle de feedback</title><rect width="50" height="20"/></svg>
<p><img src="logo.png" width="16" height="16" alt=""/></p>
<figure><pre>def code(): pass</pre><figcaption>Listing 1</figcaption></figure>
<p>La Figure 1.2 montre que le lead time augmente quand le travail en cours augmente, ce qui se vérifie partout.</p>
"""
CHAPITRE_SANS_FIGURE = "<h1>Chapitre sans image</h1><p>Du texte seulement, sans aucune figure.</p>"


def pdf_figures(chemin: Path) -> None:
    """Page 1 : image + légende ; page 2 : dessin vectoriel + légende ; page 3 : dessin sans légende + long
    paragraphe qui commence par « Figure 3.2 » ; page 4 : texte ; une toute petite image (ornement)."""
    import pymupdf
    document = pymupdf.open()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 90), False)
    pixmap.set_rect(pixmap.irect, (200, 50, 50))
    page = document.new_page()
    page.insert_image(pymupdf.Rect(60, 100, 260, 200), pixmap=pixmap)
    page.insert_image(pymupdf.Rect(400, 100, 420, 120), pixmap=pixmap)   # ornement : 20 pt
    page.insert_textbox(pymupdf.Rect(60, 205, 400, 235), "Figure 1.1 Un diagramme inventé", fontsize=10)
    for numero in (2, 3):
        page = document.new_page()
        page.draw_rect(pymupdf.Rect(60, 100, 260, 200))
        page.draw_circle((330, 150), 40)
        page.draw_line((260, 150), (290, 150))
        if numero == 2:
            page.insert_textbox(pymupdf.Rect(60, 205, 400, 235), "Fig. 2.1 Un schéma vectoriel inventé", fontsize=10)
        else:
            long = "Figure 3.2 montre que le travail en cours influence le délai de livraison. " * 8
            assert page.insert_textbox(pymupdf.Rect(60, 210, 540, 420), long, fontsize=9) > 0
    page = document.new_page()
    page.insert_textbox(pymupdf.Rect(60, 60, 540, 200), "Une page de texte sans aucune figure. " * 6, fontsize=10)
    document.save(str(chemin))
    document.close()


def pdf_scanne(chemin: Path) -> None:
    import pymupdf
    document = pymupdf.open()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 140), False)
    pixmap.set_rect(pixmap.irect, (240, 240, 240))
    for _ in range(2):
        page = document.new_page()
        page.insert_image(page.rect, pixmap=pixmap)   # image pleine page, aucun texte
    document.save(str(chemin))
    document.close()


class Base(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = self.tmp / "livres"
        self.dst = self.tmp / "sortie"
        self.src.mkdir()
        self.liste = self.tmp / "figures-a-refaire.txt"   # jamais le vrai ~/PMZilla-Lab/figures-a-refaire.txt
        patch = mock.patch.object(cb, "LISTE_A_REFAIRE", self.liste)
        patch.start()
        self.addCleanup(patch.stop)

    def empreintes(self) -> dict:
        return {str(p.relative_to(self.src)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.src.rglob("*")) if p.is_file()}

    def lancer(self, *arguments) -> str:
        arguments = arguments or (str(self.src), str(self.dst))
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["convert_books.py", "--figure-statistics", *arguments]), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(io.StringIO()):
            cb.main()
        return sortie.getvalue()

    @staticmethod
    def ligne(sortie: str, nom: str) -> list[str]:
        return next(l for l in sortie.splitlines() if l.startswith(nom)).split()


class Epub(Base):
    def test_unites_d_un_epub(self):
        base.epub(self.src / "figures.epub", "Livre à figures", [("Un", CHAPITRE_FIGURES)])
        stats = cb.figure_stats_epub(self.src / "figures.epub")
        self.assertEqual(stats["format"], "EPUB")
        self.assertEqual(stats["visuels"], 5)         # 2 <figure> avec image, 2 images isolées, 1 svg
        self.assertEqual(stats["vecteurs"], 1)        # le svg
        self.assertEqual(stats["legendes_num"], 2)    # figcaption « Figure 1.1 » et paragraphe suivant « Figure 1.2 »
        self.assertEqual(stats["legendes"], 2)        # « Listing 1 » (figure sans image) et le renvoi « La Figure 1.2 montre » : non
        self.assertEqual(stats["alt"], 3)             # alt rempli (figure, image isolée) et titre du svg ; les deux alt vides non
        self.assertEqual((stats["alt_utiles"], stats["alt_inutiles"]), (2, 1))
        self.assertEqual(stats["raisons"], {"court": 1})   # « Cycle de feedback » : 3 mots, sans légende
        self.assertEqual(stats["exploitables"], 2)    # blocs qui seraient créés : légende ou alt utile
        self.assertEqual(stats["ornements"], 1)       # logo de 16 px

    def test_legende_au_dessus_ne_vole_pas_l_image_suivante(self):
        base.epub(self.src / "deux.epub", "Deux images", [(
            "Un", '<p><img src="a.png" alt=""/></p><p>Figure 2.1 Légende de la première</p>'
                  '<p><img src="b.png" alt=""/></p><p>Texte ordinaire.</p>')])
        stats = cb.figure_stats_epub(self.src / "deux.epub")
        self.assertEqual((stats["visuels"], stats["legendes_num"], stats["exploitables"]), (2, 1, 1))

    def test_figcaption_sans_numero_et_classe_de_legende(self):
        base.epub(self.src / "legendes.epub", "Légendes", [(
            "Un", '<figure><img src="a.png" alt=""/><figcaption>Le flux de valeur</figcaption></figure>'
                  '<div><img src="b.png" alt=""/></div><p class="legende">Les quatre états</p>'
                  '<div><img src="c.png" alt=""/> Figure 3 Légende dans le même bloc</div>')])
        stats = cb.figure_stats_epub(self.src / "legendes.epub")
        self.assertEqual((stats["visuels"], stats["legendes"], stats["legendes_num"]), (3, 3, 1))

    def test_variantes_de_libelle(self):
        for texte, attendu in (("Figure 1.2 Titre", True), ("Fig. 3-4 Titre", True), ("FIGURE 12 : titre", True),
                               ("Exhibit 5 Titre", True), ("Schéma 2 Titre", True), ("Figure A.3 Titre", True),
                               ("Figure 1.2a Titre", True), ("Figure sans numéro", False), ("La figure 1.2 montre", False),
                               ("Tableau 1.1 Titre", False), ("Figures 1", False)):
            with self.subTest(texte):
                self.assertEqual(bool(cb.LABEL.match(texte)), attendu)

    def test_couverture_exclue_et_livre_sans_figure(self):
        from ebooklib import epub as lib
        livre = lib.EpubBook()
        livre.set_identifier("x")
        livre.set_title("Sans figure")
        livre.set_language("fr")
        couverture = lib.EpubHtml(title="c", file_name="cover.xhtml", lang="fr")
        couverture.content = '<html><body><img src="cover.png" alt=""/></body></html>'
        texte = lib.EpubHtml(title="t", file_name="chap1.xhtml", lang="fr")
        texte.content = f"<html><body>{CHAPITRE_SANS_FIGURE}</body></html>"
        for item in (couverture, texte):
            livre.add_item(item)
        livre.add_item(lib.EpubNcx())
        livre.add_item(lib.EpubNav())
        livre.spine = ["nav", couverture, texte]
        lib.write_epub(str(self.src / "sans.epub"), livre)
        stats = cb.figure_stats_epub(self.src / "sans.epub")
        self.assertEqual((stats["visuels"], stats["exploitables"]), (0, 0))


class Pdf(Base):
    def test_image_vecteur_legendes_et_ornement(self):
        pdf_figures(self.src / "pdf.pdf")
        stats = cb.figure_stats_pdf(self.src / "pdf.pdf")
        self.assertEqual(stats["pages"], 4)
        self.assertEqual(stats["visuels"], 3)         # image, dessin avec légende, dessin sans légende
        self.assertEqual(stats["vecteurs"], 2)
        self.assertEqual(stats["legendes_num"], 2)    # « Figure 1.1 » et « Fig. 2.1 » ; le long paragraphe n'est pas une légende
        self.assertEqual(stats["exploitables"], 2)
        self.assertEqual(stats["ornements"], 1)       # l'image de 20 pt
        self.assertEqual(stats["scannees"], 0)

    def test_page_scannee_n_est_pas_une_figure(self):
        pdf_scanne(self.src / "scan.pdf")
        stats = cb.figure_stats_pdf(self.src / "scan.pdf")
        self.assertEqual((stats["visuels"], stats["scannees"], stats["pages"]), (0, 2, 2))

    def test_pdf_de_texte_seul(self):
        base.pdf(self.src / "texte.pdf", 2, base.PHRASE * 10)
        stats = cb.figure_stats_pdf(self.src / "texte.pdf")
        self.assertEqual((stats["visuels"], stats["legendes_num"]), (0, 0))


class Rapport(Base):
    def setUp(self):
        super().setUp()
        base.epub(self.src / "a-epub-figures.epub", "A", [("Un", CHAPITRE_FIGURES)])
        base.epub(self.src / "b-epub-sans-figure.epub", "B", [("Un", CHAPITRE_SANS_FIGURE)])
        pdf_figures(self.src / "c-pdf-figures.pdf")
        pdf_scanne(self.src / "d-pdf-scanne.pdf")
        (self.src / "e-epub-casse.epub").write_bytes(b"ceci n'est pas un epub")
        (self.src / "f-pdf-casse.pdf").write_bytes(b"ceci n'est pas un pdf")
        base.epub(self.src / "g-double.epub", "G", [("Un", CHAPITRE_SANS_FIGURE)])
        pdf_figures(self.src / "g-double.pdf")                                  # ignoré : l'EPUB existe
        (self.src / "h-repli.epub").write_bytes(b"ceci n'est pas un epub")
        pdf_figures(self.src / "h-repli.pdf")                                   # remplace l'EPUB en échec
        self.avant = self.empreintes()
        self.sortie = self.lancer()

    def parties(self):
        detail, agregat = self.sortie.split("==== AGRÉGAT")
        return detail, "==== AGRÉGAT" + agregat

    def test_agregat_en_dernier_separe_du_detail_et_sans_titre(self):
        detail, agregat = self.parties()
        self.assertIn("==== DÉTAIL PAR LIVRE ====", detail)
        self.assertTrue(self.sortie.index("DÉTAIL PAR LIVRE") < self.sortie.index("AGRÉGAT"))
        self.assertIn("aucun titre de livre", agregat.splitlines()[0])
        for nom in ("a-epub-figures", "b-epub-sans-figure", "c-pdf-figures", "d-pdf-scanne", "e-epub-casse",
                    "g-double", "h-repli", str(self.src)):
            self.assertNotIn(nom, agregat)               # aucun titre ni chemin dans la partie à copier
        for nom in ("a-epub-figures", "c-pdf-figures", "h-repli"):
            self.assertIn(nom, detail)                   # ... mais le détail les nomme
        self.assertTrue(self.sortie.rstrip().splitlines()[-1].startswith("Lecture :"))   # l'agrégat est bien la fin

    def test_tableau_par_livre(self):
        detail, _ = self.parties()
        ligne = self.ligne(detail, "a-epub-figures")
        self.assertEqual(ligne[1:10], ["EPUB", "5", "1", "2", "2", "3", "1", "2", "40"])   # visuels, vect., n°, légende, alt, alt inutiles, exploit., part
        self.assertEqual(self.ligne(detail, "b-epub-sans-figure")[1:4], ["EPUB", "0", "0"])
        self.assertEqual(self.ligne(detail, "c-pdf-figures")[1:7], ["PDF", "3", "2", "2", "2", "0"])
        self.assertIn("2 page(s) scannée(s)", next(l for l in detail.splitlines() if l.startswith("d-pdf-scanne")))
        self.assertIn("ERREUR", next(l for l in detail.splitlines() if l.startswith("e-epub-casse")))
        self.assertIn("ERREUR", next(l for l in detail.splitlines() if l.startswith("f-pdf-casse")))
        self.assertIn("repli sur le PDF", next(l for l in detail.splitlines() if l.startswith("h-repli")))
        self.assertNotIn("g-double  PDF", detail)        # le PDF dont l'EPUB existe n'a pas sa ligne

    def test_agregat_par_format_et_total(self):
        _, agregat = self.parties()
        epub, pdf, total = (agregat.split("-- EPUB --")[1].split("-- PDF --")[0],
                            agregat.split("-- PDF --")[1].split("-- TOTAL")[0], agregat.split("-- TOTAL")[1])
        self.assertIn("Livres analysés : 3 (en erreur : 1)", epub)             # a, b, g ; e en erreur
        self.assertIn("Livres sans aucun visuel : 2", epub)                    # b et g
        self.assertIn("Livres avec au moins 1 légende numérotée : 1", epub)
        self.assertIn("Livres avec au moins 10 légendes numérotées : 0", epub)
        self.assertIn("Visuels : 5 (dont vectoriels : 1)", epub)
        self.assertIn("Textes alternatifs non vides : 3 · utiles : 2 · inutiles : 1 "
                      "(fichier : 0 · générique : 0 · court : 1) · seuil : 4 mots sans légende", epub)
        self.assertIn("Textes alternatifs identiques répétés au moins 3 fois", epub)
        self.assertIn("; PDF : légende numérotée) : 2 (40 % des visuels)", epub)
        self.assertIn("Visuels écartés (ni légende ni texte alternatif utile) : 3", epub)
        self.assertIn("médiane 40 %", epub)
        self.assertIn("Répartition des livres par part retenue : 0 % : 0 · 1 à 24 % : 0 · 25 à 49 % : 1 · 50 à 74 % : 0", epub)
        self.assertNotIn("Textes alternatifs", pdf)
        self.assertIn("Livres analysés : 3 (en erreur : 1)", pdf)              # c, d, h (repli) ; f en erreur
        self.assertIn("Visuels : 6 (dont vectoriels : 4)", pdf)                # c et h : 3 chacun
        self.assertIn("Pages scannées (image pleine page sans texte, non comptées) : 2 dans 1 livre(s)", pdf)
        self.assertIn("Livres analysés : 6", total)
        self.assertIn("Visuels : 11 · blocs figure qui seraient créés : 6 (55 %)", total)
        self.assertIn("Visuels écartés (candidats d'un éventuel niveau 2) : 5", total)
        self.assertIn("PDF ignorés car l'EPUB existe : 1", total)

    def test_rien_n_est_modifie_ni_ecrit_en_dehors_du_rapport(self):
        self.assertEqual(self.empreintes(), self.avant)                         # aucun livre modifié
        self.assertEqual(sorted(p.name for p in self.dst.rglob("*")), ["_statistiques_figures.txt"])
        self.assertEqual(list(self.dst.rglob("*.md")), [])                      # aucune conversion
        self.assertEqual((self.dst / "_statistiques_figures.txt").read_text(encoding="utf-8"), self.sortie)

    def test_deuxieme_lancement_identique_et_sans_trace(self):
        seconde = self.lancer()
        self.assertEqual(seconde.split("\n", 1)[1], self.sortie.split("\n", 1)[1])   # hors ligne de date
        self.assertEqual(self.empreintes(), self.avant)


class ListeAFaire(Rapport):
    """~/PMZilla-Lab/figures-a-refaire.txt (ici un fichier temporaire) : les livres à refaire, avec leur nombre de figures."""

    def lignes(self) -> list[str]:
        return self.liste.read_text(encoding="utf-8").splitlines()

    def test_une_ligne_par_livre_ayant_au_moins_une_figure_retenue(self):
        livres = [l for l in self.lignes() if not l.startswith("#")]
        self.assertEqual(livres, ["a-epub-figures.epub  # 2 figures", "c-pdf-figures.pdf  # 2 figures",
                                  "h-repli.epub  # 2 figures"])
        for ecarte in ("b-epub-sans-figure", "d-pdf-scanne", "e-epub-casse", "f-pdf-casse", "g-double"):
            self.assertNotIn(ecarte, self.liste.read_text(encoding="utf-8"))    # sans figure retenue, en erreur ou doublon PDF

    def test_chemin_relatif_au_dossier_des_livres_avec_extension(self):
        base.epub(self.src / "03 Lean" / "sous-dossier" / "i-epub.epub", "I", [("Un", CHAPITRE_FIGURES)])
        self.lancer()
        self.assertIn("03 Lean/sous-dossier/i-epub.epub  # 2 figures", self.lignes())

    def test_la_liste_se_relit_par_refaire_figures_commentaires_ignores(self):
        livres = sorted(p for p in self.src.rglob("*") if p.suffix.lower() in (".pdf", ".epub"))
        choisis, problemes = cb.choose_books([f"@{self.liste}"], livres, self.src)
        self.assertEqual(problemes, [])
        self.assertEqual([p.name for p in choisis], ["a-epub-figures.epub", "c-pdf-figures.pdf", "h-repli.epub"])
        direct, _ = cb.choose_books(["a-epub-figures.epub  # 2 figures"], livres, self.src)   # commentaire en fin de ligne
        self.assertEqual([p.name for p in direct], ["a-epub-figures.epub"])

    def test_un_dieze_dans_un_nom_n_est_pas_un_commentaire(self):
        base.epub(self.src / "C# en pratique.epub", "C", [("Un", CHAPITRE_FIGURES)])
        livres = sorted(p for p in self.src.rglob("*") if p.suffix.lower() in (".pdf", ".epub"))
        choisis, problemes = cb.choose_books(["C# en pratique.epub  # 2 figures"], livres, self.src)
        self.assertEqual((problemes, [p.name for p in choisis]), ([], ["C# en pratique.epub"]))

    def test_fichier_remplace_a_chaque_lancement_et_aucun_livre_modifie(self):
        self.liste.write_text("ANCIEN CONTENU", encoding="utf-8")
        self.lancer()
        self.assertNotIn("ANCIEN", self.liste.read_text(encoding="utf-8"))
        self.assertEqual(self.empreintes(), self.avant)

    def test_dossier_sans_livre_ecrit_une_liste_sans_ligne_de_livre(self):
        for livre in list(self.src.iterdir()):
            livre.unlink()
        self.lancer()
        self.assertTrue(all(l.startswith("#") for l in self.lignes()))


class Cadre(Base):
    def test_arguments_et_dossier_absent(self):
        with self.assertRaises(SystemExit) as erreur:
            with mock.patch.object(sys, "argv", ["convert_books.py", "--figure-statistics"]), \
                    contextlib.redirect_stdout(io.StringIO()):
                cb.main()
        self.assertEqual(erreur.exception.code, 1)
        with self.assertRaises(SystemExit):
            self.lancer(str(self.tmp / "absent"), str(self.dst))

    def test_dossier_de_sortie_par_defaut_dans_le_workspace(self):
        base.pdf(self.src / "t.pdf", 1, base.PHRASE * 5)
        with mock.patch.object(cb, "WORKSPACE", self.tmp / "ws"):
            self.lancer(str(self.src))
        self.assertTrue((self.tmp / "ws" / "Bibliotheque-MD" / "_statistiques_figures.txt").exists())

    def test_dossier_sans_livre(self):
        sortie = self.lancer()
        self.assertIn("TOTAL (EPUB + PDF)", sortie)
        self.assertIn("Livres analysés : 0", sortie)

    def test_fichier_interdit_en_lecture_a_claude_code(self):
        deny = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"]
        self.assertIn("Read(**/_statistiques_figures.txt)", deny)
        for commande in ("cat", "head", "tail", "less", "more", "grep", "awk", "sed", "cp"):
            self.assertIn(f"Bash({commande} *_statistiques_figures.txt*)", deny)


if __name__ == "__main__":
    unittest.main()
