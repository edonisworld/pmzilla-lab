"""
Tests de l'étape 1 des figures dans `convert_books.py` : blocs de figures dans le Markdown, filtre des textes
alternatifs, images extraites seulement pour les figures retenues, option --redo-figures.

    uv run --with pymupdf4llm --with ebooklib --with markdownify --with beautifulsoup4 \
        python -m unittest discover -s tests/convert_books -v

Livres fabriqués dans un dossier temporaire (EPUB avec images, PDF avec image et dessin vectoriel) ; le dossier des
images est remplacé par un dossier temporaire : jamais le vrai Bibliotheque-Images, Bibliotheque-MD ni un livre réel.
"""
import contextlib
import io
import json
import re
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
import test_convert_books as base  # noqa: E402
import test_statistiques_figures as figures  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]


def png(couleur: tuple[int, int, int], largeur: int = 60, hauteur: int = 40) -> bytes:
    import pymupdf
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, largeur, hauteur), False)
    pixmap.set_rect(pixmap.irect, couleur)
    return pixmap.tobytes("png")


ROUGE, VERT, BLEU, JAUNE = png((200, 30, 30)), png((30, 200, 30)), png((30, 30, 200)), png((220, 220, 30))

CHAPITRE = """
<h1>Chapitre un</h1>
<p>Un premier paragraphe de texte courant, avant toute figure.</p>
<figure><img src="../images/a.png" alt="Trois colonnes d'un tableau kanban"/><figcaption>Figure 1.1 Un tableau kanban</figcaption></figure>
<p><img src="../images/b.png" alt="Courbe montrant le lead time par semaine"/></p>
<p><img src="../images/c.png" alt=""/></p>
<p><img src="../images/d.png" alt="image"/></p>
<p><img src="../images/e.png" alt="IMG_0042.png"/></p>
<p>Figure 1.2 Une légende sous l'image du fichier</p>
<p><img src="../images/f.png" alt="Logo"/></p>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"><title>Un cycle de feedback complet</title><rect width="50" height="20"/></svg>
<p><img src="../images/absente.png" alt="Une image absente du livre avec une légende"/></p>
<p>Figure 1.3 Légende d'une image que le livre ne contient pas</p>
<p><img src="data:image/png;base64,{donnee}" alt=""/></p>
<p>Figure 1.4 Légende d'une image en ligne</p>
<p>Un dernier paragraphe de texte courant, après les figures.</p>
"""


def epub_images(chemin: Path, chapitre: str = CHAPITRE, titre: str = "Livre à figures") -> None:
    import base64
    from ebooklib import epub as lib
    livre = lib.EpubBook()
    livre.set_identifier("id-" + chemin.stem)
    livre.set_title(titre)
    livre.set_language("fr")
    page = lib.EpubHtml(title="Un", file_name="text/chap1.xhtml", lang="fr")
    page.content = "<html><body>" + chapitre.replace("{donnee}", base64.b64encode(JAUNE).decode()) + "</body></html>"
    livre.add_item(page)
    for nom, octets in (("a", ROUGE), ("b", VERT), ("c", BLEU), ("d", ROUGE), ("e", VERT), ("f", BLEU)):
        livre.add_item(lib.EpubItem(uid=f"img-{nom}", file_name=f"images/{nom}.png", media_type="image/png",
                                    content=octets))
    livre.toc = (page,)
    livre.add_item(lib.EpubNcx())
    livre.add_item(lib.EpubNav())
    livre.spine = ["nav", page]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    lib.write_epub(str(chemin), livre)


class Base(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src, self.dst, self.images = self.tmp / "livres", self.tmp / "md", self.tmp / "images"
        self.src.mkdir()
        patch = mock.patch.object(cb, "IMAGES_DIR", self.images)
        patch.start()
        self.addCleanup(patch.stop)
        liste = mock.patch.object(cb, "LISTE_A_REFAIRE", self.tmp / "figures-a-refaire.txt")   # jamais le vrai fichier
        liste.start()
        self.addCleanup(liste.stop)

    def preparer(self) -> None:
        """La conversion normale réécrit le Markdown existant de chaque livre : un Markdown « ANCIEN » est posé, au
        chemin de la source, pour chaque livre qui n'en a pas encore."""
        livres = sorted(p for p in self.src.rglob("*") if p.suffix.lower() in (".pdf", ".epub"))
        for livre in cb.preferred_books(livres, self.src):
            md = self.dst / livre.relative_to(self.src).with_suffix(".md")
            if not md.exists():
                md.parent.mkdir(parents=True, exist_ok=True)
                md.write_text("ANCIEN", encoding="utf-8")

    def lancer(self, *supplement, preparer: bool = True) -> str:
        if not supplement and preparer:
            self.preparer()
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["convert_books.py", str(self.src), str(self.dst), *supplement]), \
                contextlib.redirect_stdout(sortie):
            cb.main()
        return sortie.getvalue()

    def md(self, nom: str) -> str:
        return (self.dst / f"{nom}.md").read_text(encoding="utf-8")

    def fichiers_images(self, livre: str) -> list[str]:
        dossier = self.images / livre
        return sorted(p.name for p in dossier.iterdir()) if dossier.exists() else []


class FiltreDesTextesAlternatifs(unittest.TestCase):
    def test_etats(self):
        cas = [  # (texte alternatif, légende à côté ?, état attendu)
            ("", False, None), ("   ", True, None),
            ("IMG_0042.png", False, "fichier"), ("cover.jpg", True, "fichier"), ("fig_12", False, "fichier"),
            ("image001", False, "fichier"), ("Figure-3-2.SVG", True, "fichier"), ("images/a.png", False, "fichier"),
            ("Figure 1.jpg", True, "fichier"), ("a3f5c9d8e1b24f60", False, "fichier"),
            ("image", False, "générique"), ("Figure 1", True, "générique"), ("photo", True, "générique"),
            ("Logo", True, "générique"), ("Icône", False, "générique"), ("un logo", False, "générique"),
            ("Illustration 3", False, "générique"), ("image of", False, "générique"),
            ("image image image image", False, "générique"), ("Figure 1.2", False, "générique"),
            ("Trois colonnes", False, "court"), ("Un tableau kanban", False, "court"), ("Kanban", False, "court"),
            ("Logo Quantelis", False, "court"),
            ("Courbe du lead time", False, "utile"), ("Un tableau kanban", True, "utile"),
            ("Kanban", True, "utile"), ("Logo Quantelis", True, "utile"),
            ("Logo Quantelis Healthcare France", False, "utile"),
            ("Four columns of a kanban board", False, "utile"),
        ]
        for alt, legende, attendu in cas:
            with self.subTest(alt=alt, legende=legende):
                self.assertEqual(cb.alt_status(alt, legende), attendu)

    def test_seuil_de_quatre_mots_sans_legende(self):
        self.assertEqual(cb.MIN_ALT_WORDS, 4)
        self.assertEqual(cb.alt_status("une courbe du lead", False), "utile")   # 4 mots : retenu
        self.assertEqual(cb.alt_status("courbe du lead", False), "court")       # 3 mots : écarté
        self.assertEqual(cb.alt_status("courbe du lead", True), "utile")        # avec légende : retenu
        with mock.patch.object(cb, "MIN_ALT_WORDS", 2):                          # le seuil se règle en un endroit
            self.assertEqual(cb.alt_status("Trois colonnes", False), "utile")


class EpubBlocs(Base):
    def setUp(self):
        super().setUp()
        epub_images(self.src / "figures.epub", CHAPITRE)
        self.sortie = self.lancer()
        self.md_texte = self.md("figures")

    def test_seules_les_figures_retenues_deviennent_des_blocs(self):
        blocs = re.findall(r"<!-- figure (.*?) -->\n((?:(?:Légende|Texte alternatif) : .*\n?)*)", self.md_texte)
        self.assertEqual(len(blocs), 6)
        self.assertEqual([re.search(r"id=(fig-\d+)", b[0]).group(1) for b in blocs],
                         [f"fig-{n:04d}" for n in range(1, 7)])
        self.assertIn("figures: 6", self.md_texte.split("---")[1])
        # figure avec légende et texte alternatif utile
        self.assertIn('<!-- figure id=fig-0001 source=epub image="Bibliotheque-Images/figures/fig-0001.png" -->\n'
                      "Légende : Figure 1.1 Un tableau kanban\n"
                      "Texte alternatif : Trois colonnes d'un tableau kanban", self.md_texte)
        # image sans légende mais avec un texte alternatif utile
        self.assertIn('id=fig-0002 source=epub image="Bibliotheque-Images/figures/fig-0002.png" -->\n'
                      "Texte alternatif : Courbe montrant le lead time par semaine", self.md_texte)
        # nom de fichier en alt, mais légende voisine : la légende suffit, l'alt inutile n'est pas recopié
        self.assertIn("Légende : Figure 1.2 Une légende sous l'image du fichier\n", self.md_texte)
        self.assertNotIn("IMG_0042", self.md_texte)
        # svg en ligne : son titre est utile (5 mots)
        self.assertIn("Texte alternatif : Un cycle de feedback complet", self.md_texte)

    def test_ce_qui_est_ecarte_ne_laisse_aucune_trace(self):
        # sans alt, alt « image », alt « Logo » : ni bloc, ni image
        self.assertEqual(self.md_texte.count("<!-- figure"), 6)
        self.assertNotIn("Texte alternatif : image", self.md_texte)
        self.assertNotIn("Texte alternatif : Logo", self.md_texte)
        self.assertNotIn("@@FIG", self.md_texte)     # aucun marqueur provisoire ne reste
        self.assertNotIn("![", self.md_texte)         # aucune image Markdown

    def test_legendes_voisines_ne_sont_pas_dupliquees_dans_le_texte(self):
        for legende in ("Figure 1.2 Une légende sous l'image du fichier",
                        "Figure 1.3 Légende d'une image que le livre ne contient pas",
                        "Figure 1.4 Légende d'une image en ligne"):
            self.assertEqual(self.md_texte.count(legende), 1, legende)
        self.assertIn("Un premier paragraphe de texte courant, avant toute figure.", self.md_texte)
        self.assertIn("Un dernier paragraphe de texte courant, après les figures.", self.md_texte)
        # l'ordre du livre est respecté
        positions = [self.md_texte.index(t) for t in ("avant toute figure", "id=fig-0001", "id=fig-0002", "id=fig-0003",
                                                       "id=fig-0004", "id=fig-0005", "id=fig-0006", "après les figures")]
        self.assertEqual(positions, sorted(positions))

    def test_images_extraites_seulement_pour_les_figures_retenues(self):
        # fig-0001 (a.png), fig-0002 (b.png), fig-0003 (e.png, légende), fig-0004 (svg), fig-0005 (absente : aucune
        # image), fig-0006 (image en ligne). Les images c, d, f (écartées) ne sont jamais extraites.
        self.assertEqual(self.fichiers_images("figures"),
                         ["fig-0001.png", "fig-0002.png", "fig-0003.png", "fig-0004.svg", "fig-0006.png"])
        dossier = self.images / "figures"
        self.assertEqual((dossier / "fig-0001.png").read_bytes(), ROUGE)
        self.assertEqual((dossier / "fig-0002.png").read_bytes(), VERT)
        self.assertEqual((dossier / "fig-0003.png").read_bytes(), VERT)    # e.png
        self.assertEqual((dossier / "fig-0006.png").read_bytes(), JAUNE)   # image « data: »
        svg = (dossier / "fig-0004.svg").read_text(encoding="utf-8")
        self.assertIn("viewBox=", svg)
        self.assertIn("xmlns=", svg)
        for octets in (BLEU,):
            self.assertNotIn(octets, [p.read_bytes() for p in dossier.glob("*.png")])   # c.png et f.png : bleu
        # figure retenue mais image introuvable : bloc sans chemin
        absente = re.search(r"<!-- figure (id=fig-0005[^>]*) -->", self.md_texte).group(1)
        self.assertNotIn("image=", absente)

    def test_rapport_de_conversion(self):
        self.assertIn("Blocs figure créés : 6 (images extraites : 5, dans Bibliotheque-Images/)", self.sortie)
        rapport = (self.dst / "_rapport_conversion.txt").read_text(encoding="utf-8")
        self.assertIn("figures.epub : 6 bloc(s) figure, 5 image(s)", rapport)

    def test_livre_sans_figure_retenue(self):
        epub_images(self.src / "sans.epub", '<p>Du texte.</p><p><img src="../images/c.png" alt=""/></p>'
                                            + "<p>Plus de texte pour dépasser le seuil de longueur.</p>" * 40, "Sans")
        self.lancer()
        self.assertIn("figures: 0", self.md("sans").split("---")[1])
        self.assertNotIn("<!-- figure", self.md("sans"))
        self.assertFalse((self.images / "sans").exists())      # aucun dossier d'images pour un livre sans figure retenue

    def test_texte_courant_identique_hors_figures(self):
        """Hors blocs, le texte du livre est celui que produisait l'ancienne conversion (figures supprimées)."""
        sans_figure = re.sub(r"\n*<!-- figure .*?(?=\n\n|\Z)", "", self.md_texte, flags=re.S)
        for phrase in ("Chapitre un", "avant toute figure", "après les figures"):
            self.assertIn(phrase, sans_figure)


class PdfBlocs(Base):
    def setUp(self):
        super().setUp()
        figures.pdf_figures(self.src / "schemas.pdf")
        self.sortie = self.lancer()
        self.md_texte = self.md("schemas")

    def test_seuls_les_visuels_a_legende_numerotee_deviennent_des_blocs(self):
        self.assertEqual(self.md_texte.count("<!-- figure"), 2)
        self.assertIn("figures: 2", self.md_texte.split("---")[1])
        # image intégrée, page 1 ; zone vectorielle, page 2
        self.assertIn('<!-- figure id=fig-0001 source=pdf page=1 image="Bibliotheque-Images/schemas/fig-0001.png" -->\n'
                      "Légende : Figure 1.1 Un diagramme inventé", self.md_texte)
        self.assertIn('<!-- figure id=fig-0002 source=pdf page=2 image="Bibliotheque-Images/schemas/fig-0002.png" -->\n'
                      "Légende : Fig. 2.1 Un schéma vectoriel inventé", self.md_texte)
        # la zone vectorielle de la page 3 n'a pas de légende (le long paragraphe « Figure 3.2 » n'en est pas une)
        self.assertNotIn("Figure 3.2 montre que le travail en cours influence le délai de livraison. Figure 3.2",
                         " ".join(re.findall(r"Légende : .*", self.md_texte)))
        self.assertNotIn("page=3", self.md_texte)

    def test_images_rendues_seulement_pour_les_figures_retenues(self):
        self.assertEqual(self.fichiers_images("schemas"), ["fig-0001.png", "fig-0002.png"])
        for nom in ("fig-0001.png", "fig-0002.png"):
            octets = (self.images / "schemas" / nom).read_bytes()
            self.assertEqual(octets[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(len(octets), 200)
        # l'image rendue de la figure vectorielle est plus grande qu'une vignette (150 dpi)
        import pymupdf
        rendu = pymupdf.Pixmap(str(self.images / "schemas" / "fig-0002.png"))
        self.assertGreater(rendu.width, 300)

    def test_blocs_apres_le_texte_de_leur_page_et_texte_inchange(self):
        # le texte de la page 4 vient après les blocs des pages 1 et 2
        self.assertLess(self.md_texte.index("id=fig-0002"), self.md_texte.index("Une page de texte sans aucune figure"))
        sans_blocs = re.sub(r"\n<!-- figure [^\n]*-->\nLégende : [^\n]*\n\n", "", self.md_texte)
        import pymupdf4llm
        brut = pymupdf4llm.to_markdown(str(self.src / "schemas.pdf"))
        self.assertEqual(sans_blocs.split("---\n", 2)[2].strip(), brut.strip())

    def test_pdf_sans_legende_numerotee_est_converti_comme_avant(self):
        base.pdf(self.src / "texte.pdf", 2, base.PHRASE * 12)
        self.lancer()
        self.assertIn("figures: 0", self.md("texte").split("---")[1])
        self.assertFalse((self.images / "texte").exists())

    def test_rapport(self):
        self.assertIn("Blocs figure créés : 2 (images extraites : 2", self.sortie)


class RefaireLesFigures(Base):
    def setUp(self):
        super().setUp()
        epub_images(self.src / "a.epub", CHAPITRE, "Livre A")
        base.pdf(self.src / "b.pdf", 2, base.PHRASE * 12)
        # état « avant » : un ancien Markdown et d'anciennes images, sans figures
        self.dst.mkdir()
        (self.dst / "a.md").write_text("ANCIEN CONTENU DE A", encoding="utf-8")
        (self.dst / "b.md").write_text("ANCIEN CONTENU DE B", encoding="utf-8")
        (self.images / "a").mkdir(parents=True)
        (self.images / "a" / "fig-9999.png").write_bytes(b"ancienne image")

    def test_la_conversion_normale_reecrit_tout_sur_place_avec_sauvegarde(self):
        sortie = self.lancer()
        self.assertIn("<!-- figure id=fig-0001", self.md("a"))
        self.assertTrue(self.md("b").startswith("---"))                           # le PDF aussi, sur place
        self.assertEqual((self.dst / "a.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN CONTENU DE A")
        self.assertEqual((self.dst / "b.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN CONTENU DE B")
        self.assertIn("Convertis : 2", sortie)
        self.assertNotIn("fig-9999.png", self.fichiers_images("a"))

    def test_refaire_un_livre_sauvegarde_remplace_et_ne_touche_pas_aux_autres(self):
        sortie = self.lancer("--redo-figures", "a")
        self.assertIn("<!-- figure id=fig-0001", self.md("a"))
        self.assertEqual((self.dst / "a.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN CONTENU DE A")
        self.assertEqual(self.md("b"), "ANCIEN CONTENU DE B")                  # non désigné : intact
        self.assertFalse((self.dst / "b.md.avant-figures").exists())
        self.assertNotIn("fig-9999.png", self.fichiers_images("a"))            # anciennes images retirées
        self.assertEqual(len(self.fichiers_images("a")), 5)
        self.assertIn("Refaits (figures) : 1", sortie)
        self.assertIn("Anciennes versions gardées (.md.avant-figures) : 1", sortie)
        self.assertIn("À faire ensuite : relancer sort_by_domain.py", sortie)
        self.assertTrue((self.dst / "_rapport_figures.txt").exists())
        self.assertFalse((self.dst / "_rapport_conversion.txt").exists())      # le rapport complet n'est pas écrasé

    def test_la_sauvegarde_n_est_faite_qu_une_fois(self):
        self.lancer("--redo-figures", "a")
        premier = self.md("a")
        self.lancer("--redo-figures", "a")
        self.assertEqual((self.dst / "a.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN CONTENU DE A")
        self.assertEqual(self.md("a"), premier)

    def test_formes_de_noms_et_liste(self):
        liste = self.tmp / "liste.txt"
        liste.write_text("# livres à refaire\n\nb.pdf\n", encoding="utf-8")
        sortie = self.lancer("--redo-figures", "A.EPUB", f"@{liste}")
        self.assertIn("Refaits (figures) : 2", sortie)
        self.assertIn("<!-- figure", self.md("a"))
        self.assertIn("figures: 0", self.md("b").split("---")[1])
        self.assertTrue((self.dst / "b.md.avant-figures").exists())

    def test_epub_prefere_au_pdf_du_meme_livre(self):
        base.pdf(self.src / "a.pdf", 1, base.PHRASE * 12)
        self.lancer("--redo-figures", "a")
        self.assertIn('source: "a.epub"', self.md("a"))

    def test_nom_introuvable_ou_ambigu_arrete_avant_toute_conversion(self):
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--redo-figures", "a", "inconnu")
        self.assertIn("rien n'a été converti", str(erreur.exception.code))
        self.assertIn("introuvable : inconnu", str(erreur.exception.code))
        self.assertEqual(self.md("a"), "ANCIEN CONTENU DE A")                  # même « a », pourtant valide : rien fait
        self.assertFalse((self.dst / "a.md.avant-figures").exists())
        epub_images(self.src / "x" / "doublon.epub", CHAPITRE, "X")
        epub_images(self.src / "y" / "doublon.epub", CHAPITRE, "Y")
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--redo-figures", "doublon")
        self.assertIn("ambigu : doublon (", str(erreur.exception.code))
        (self.dst / "x").mkdir()
        (self.dst / "x" / "doublon.md").write_text("ANCIEN X", encoding="utf-8")
        self.lancer("--redo-figures", "x/doublon")                           # le chemin lève l'ambiguïté
        self.assertIn("<!-- figure", (self.dst / "x" / "doublon.md").read_text(encoding="utf-8"))
        self.assertEqual((self.dst / "x" / "doublon.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN X")
        self.assertFalse((self.dst / "y").exists())

    def test_option_sans_livre(self):
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--redo-figures")
        self.assertIn("au moins un livre", str(erreur.exception.code))

    def test_echec_de_la_conversion_laisse_l_ancien_markdown(self):
        (self.src / "casse.epub").write_bytes(b"ceci n'est pas un epub")
        (self.dst / "casse.md").write_text("ANCIEN CONTENU DE CASSE", encoding="utf-8")
        sortie = self.lancer("--redo-figures", "casse")
        self.assertEqual(self.md("casse"), "ANCIEN CONTENU DE CASSE")
        self.assertFalse((self.dst / "casse.md.avant-figures").exists())        # rien n'a été remplacé
        self.assertIn("Erreurs : 1", sortie)


NUMEROTE = "03 Lean, flux et Kanban"
ANCIEN = "Agile & Scrum"


class RefaireDossiersRenommes(Base):
    """Les dossiers de la source ont été renommés (« 03 Lean, flux et Kanban/ ») mais pas ceux du Markdown
    (« Agile & Scrum/ ») : le Markdown existant se retrouve par son nom de fichier et se réécrit sur place."""

    def setUp(self):
        super().setUp()
        epub_images(self.src / NUMEROTE / "cfd.epub", CHAPITRE, "CFD")
        epub_images(self.src / NUMEROTE / "autre.epub", CHAPITRE, "Autre")
        for nom in ("cfd", "autre", "intact"):
            chemin = self.dst / ANCIEN / f"{nom}.md"
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(f"ANCIEN {nom.upper()}", encoding="utf-8")

    def arbre(self) -> list[str]:
        return sorted(str(p.relative_to(self.dst)) for p in self.dst.rglob("*") if p.is_file())

    def test_reecrit_sur_place_avec_sauvegarde_et_sans_nouveau_dossier(self):
        sortie = self.lancer("--redo-figures", "cfd")
        self.assertIn("<!-- figure", (self.dst / ANCIEN / "cfd.md").read_text(encoding="utf-8"))
        self.assertEqual((self.dst / ANCIEN / "cfd.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN CFD")
        self.assertFalse((self.dst / NUMEROTE).exists())                        # aucun dossier créé sous le nouveau nom
        self.assertEqual(self.arbre(), [f"{ANCIEN}/autre.md", f"{ANCIEN}/cfd.md", f"{ANCIEN}/cfd.md.avant-figures",
                                        f"{ANCIEN}/intact.md", "_rapport_figures.txt"])
        self.assertEqual((self.dst / ANCIEN / "autre.md").read_text(encoding="utf-8"), "ANCIEN AUTRE")   # non désigné
        self.assertIn(f"{NUMEROTE}/cfd.epub -> {ANCIEN}/cfd.md", sortie)         # dit où il réécrit
        self.assertIn(f"{NUMEROTE}/cfd.epub : 6 bloc(s) figure, 5 image(s) -> {ANCIEN}/cfd.md",
                      (self.dst / "_rapport_figures.txt").read_text(encoding="utf-8"))
        self.assertEqual(sorted(p.name for p in (self.images / "cfd").iterdir())[:1], ["fig-0001.png"])

    def test_compteur_des_anciennes_versions(self):
        premiere = self.lancer("--redo-figures", "cfd", "autre")
        self.assertIn("Anciennes versions gardées (.md.avant-figures) : 2 (créées maintenant : 2, "
                      "déjà là d'un passage précédent : 0)", premiere)
        seconde = self.lancer("--redo-figures", "cfd", "autre")
        self.assertIn("Anciennes versions gardées (.md.avant-figures) : 2 (créées maintenant : 0, "
                      "déjà là d'un passage précédent : 2)", seconde)
        (self.dst / ANCIEN / "autre.md.avant-figures").unlink()
        mixte = self.lancer("--redo-figures", "cfd", "autre")
        self.assertIn("Anciennes versions gardées (.md.avant-figures) : 2 (créées maintenant : 1, "
                      "déjà là d'un passage précédent : 1)", mixte)
        self.assertEqual((self.dst / ANCIEN / "cfd.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN CFD")

    def test_markdown_introuvable_arrete_avant_toute_conversion(self):
        (self.dst / ANCIEN / "cfd.md").unlink()
        avant = self.arbre()
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--redo-figures", "autre", "cfd")                     # « autre » est valide : rien n'est fait non plus
        message = str(erreur.exception.code)
        self.assertIn("rien n'a été converti", message)
        self.assertIn(f"Markdown introuvable : {NUMEROTE}/cfd.epub", message)
        self.assertNotIn("autre.epub", message)
        self.assertEqual(self.arbre(), avant)                                    # aucun fichier créé, aucune sauvegarde
        self.assertFalse(self.images.exists())                                   # aucune image extraite

    def test_markdown_en_double_arrete_et_liste_les_chemins(self):
        double = self.dst / NUMEROTE / "cfd.md"
        double.parent.mkdir(parents=True)
        double.write_text("DOUBLON", encoding="utf-8")
        avant = self.arbre()
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--redo-figures", "cfd", "autre")
        message = str(erreur.exception.code)
        self.assertIn("rien n'a été converti", message)
        self.assertIn(f"plusieurs Markdown pour {NUMEROTE}/cfd.epub", message)
        self.assertIn(f"{ANCIEN}/cfd.md", message)
        self.assertIn(f"{NUMEROTE}/cfd.md", message)
        self.assertEqual(self.arbre(), avant)
        self.assertEqual((self.dst / ANCIEN / "autre.md").read_text(encoding="utf-8"), "ANCIEN AUTRE")
        self.assertFalse(self.images.exists())

    def test_dossiers_et_fichiers_commencant_par_underscore_sont_ignores(self):
        corbeille = self.dst / "_a_supprimer" / ANCIEN / "cfd.md"
        corbeille.parent.mkdir(parents=True)
        corbeille.write_text("A SUPPRIMER", encoding="utf-8")
        self.lancer("--redo-figures", "cfd")                                  # pas de « plusieurs Markdown »
        self.assertIn("<!-- figure", (self.dst / ANCIEN / "cfd.md").read_text(encoding="utf-8"))
        self.assertEqual(corbeille.read_text(encoding="utf-8"), "A SUPPRIMER")

    def test_la_sauvegarde_n_est_pas_un_markdown_a_part(self):
        self.lancer("--redo-figures", "cfd")
        self.lancer("--redo-figures", "cfd")                                  # cfd.md.avant-figures n'est pas pris pour un doublon
        self.assertEqual(len([p for p in self.dst.rglob("cfd*")]), 2)

    def test_la_conversion_normale_retrouve_aussi_les_markdown_des_dossiers_renommes(self):
        """Option A : la conversion normale réécrit le Markdown existant sur place, quel que soit le dossier de la
        source ; aucun dossier n'est créé sous le nouveau nom, « intact » (pas de livre) n'est pas touché."""
        sortie = self.lancer(preparer=False)
        self.assertFalse((self.dst / NUMEROTE).exists())
        self.assertIn("<!-- figure", (self.dst / ANCIEN / "cfd.md").read_text(encoding="utf-8"))
        self.assertIn("<!-- figure", (self.dst / ANCIEN / "autre.md").read_text(encoding="utf-8"))
        self.assertEqual((self.dst / ANCIEN / "intact.md").read_text(encoding="utf-8"), "ANCIEN INTACT")
        self.assertIn(f"{NUMEROTE}/cfd.epub -> {ANCIEN}/cfd.md  (voie : nom)", sortie)


ISBN = "9781942788829"
EN_TETE = '---\ntitle: "Team Topologies"\nsource: "{source}"\npages: 300\nfigures: 0\n---\n\n'


class FixtureMapping(Base):
    """Quand aucun Markdown ne porte le nom du livre (EPUB à titre d'ISBN, Markdown renommé à la main), la table
    MAPPING retrouve le Markdown : clé au nom du livre (sans casse ni accents) ou en-tête « source: »."""

    def setUp(self):
        super().setUp()
        self.dst.mkdir()
        epub_images(self.src / NUMEROTE / f"{ISBN}.epub", CHAPITRE, "Team Topologies")
        epub_images(self.src / NUMEROTE / "cfd.epub", CHAPITRE, "CFD")
        self.ecrire("Team Topologies - Skelton.md", EN_TETE.format(source=f"{ISBN}.epub") + "ANCIEN TT")
        self.ecrire(f"{ANCIEN}/cfd.md", "ANCIEN CFD")
        self.mapping = {f"md/Team Topologies - Skelton.md": "ODT", f"md/{ANCIEN}/cfd.md": "D"}
        patch = mock.patch.object(cb, "MAPPING", self.mapping)
        patch.start()
        self.addCleanup(patch.stop)

    def ecrire(self, relatif: str, texte: str) -> Path:
        chemin = self.dst / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def arbre(self) -> list[str]:
        return sorted(str(p.relative_to(self.dst)) for p in self.dst.rglob("*") if p.is_file())

    def erreur(self, *arguments) -> str:
        with self.assertRaises(SystemExit) as erreur:
            self.lancer(*arguments)
        return str(erreur.exception.code)



class RefaireParMapping(FixtureMapping):
    def test_team_topologies_retrouve_par_l_en_tete_de_la_cle(self):
        sortie = self.lancer("--redo-figures", ISBN)
        self.assertIn("<!-- figure", (self.dst / "Team Topologies - Skelton.md").read_text(encoding="utf-8"))
        self.assertEqual((self.dst / "Team Topologies - Skelton.md.avant-figures").read_text(encoding="utf-8"),
                         EN_TETE.format(source=f"{ISBN}.epub") + "ANCIEN TT")
        self.assertFalse((self.dst / f"{ISBN}.md").exists())                     # aucun Markdown à titre d'ISBN
        self.assertFalse((self.dst / NUMEROTE).exists())
        voie = "(voie : MAPPING, clé « md/Team Topologies - Skelton.md »)"
        self.assertIn(f"{NUMEROTE}/{ISBN}.epub -> Team Topologies - Skelton.md  {voie}", sortie)
        self.assertIn(f"{NUMEROTE}/{ISBN}.epub : 6 bloc(s) figure, 5 image(s) -> Team Topologies - Skelton.md {voie}",
                      (self.dst / "_rapport_figures.txt").read_text(encoding="utf-8"))
        self.assertEqual((self.dst / ANCIEN / "cfd.md").read_text(encoding="utf-8"), "ANCIEN CFD")   # non désigné

    def test_le_nom_de_fichier_d_abord_puis_mapping(self):
        sortie = self.lancer("--redo-figures", "cfd", ISBN)
        self.assertIn(f"{NUMEROTE}/cfd.epub -> {ANCIEN}/cfd.md  (voie : nom)", sortie)
        self.assertIn("(voie : MAPPING, clé", sortie)
        self.mapping[f"md/Autre/{ISBN}.md"] = "D"                                  # une clé au nom du livre, fichier absent
        self.assertIn(f"{NUMEROTE}/cfd.epub -> {ANCIEN}/cfd.md  (voie : nom)",
                      self.lancer("--redo-figures", "cfd"))                      # le nom de fichier l'emporte : MAPPING ignoré

    def test_cle_au_nom_du_livre_sans_casse_ni_accents(self):
        epub_images(self.src / "Équipes Autonomes.epub", CHAPITRE, "Équipes")
        self.ecrire("Rayon/equipes autonomes.md", "ANCIEN EQUIPES")                 # accents et casse différents
        self.mapping["md/Rayon/EQUIPES autonomes.md"] = "O"
        sortie = self.lancer("--redo-figures", "Équipes Autonomes")
        self.assertIn("-> Rayon/equipes autonomes.md  (voie : MAPPING, clé « md/Rayon/EQUIPES autonomes.md »)", sortie)
        self.assertIn("<!-- figure", (self.dst / "Rayon" / "equipes autonomes.md").read_text(encoding="utf-8"))

    def test_les_cles_d_un_autre_dossier_sont_ignorees(self):
        self.mapping.clear()
        self.mapping["autre-dossier/Team Topologies - Skelton.md"] = "ODT"
        self.assertIn("Markdown introuvable", self.erreur("--redo-figures", ISBN))

    def test_aucune_correspondance_arrete(self):
        self.mapping.clear()
        avant = self.arbre()
        message = self.erreur("--redo-figures", ISBN, "cfd")                     # « cfd » est valide : rien n'est fait non plus
        self.assertIn("rien n'a été converti", message)
        self.assertIn(f"Markdown introuvable : {NUMEROTE}/{ISBN}.epub", message)
        self.assertIn("aucune clé de MAPPING ne correspond", message)
        self.assertEqual(self.arbre(), avant)
        self.assertFalse(self.images.exists())

    def test_plusieurs_correspondances_arretent(self):
        self.ecrire("Copie/Team Topologies - copie.md", EN_TETE.format(source=f"{ISBN}.epub") + "COPIE")
        self.mapping["md/Copie/Team Topologies - copie.md"] = ""
        avant = self.arbre()
        message = self.erreur("--redo-figures", ISBN)
        self.assertIn(f"plusieurs clés de MAPPING pour {NUMEROTE}/{ISBN}.epub", message)
        self.assertIn("md/Team Topologies - Skelton.md -> Team Topologies - Skelton.md", message)
        self.assertIn("md/Copie/Team Topologies - copie.md -> Copie/Team Topologies - copie.md", message)
        self.assertEqual(self.arbre(), avant)
        self.assertFalse(self.images.exists())

    def test_cle_vers_un_fichier_absent_arrete(self):
        epub_images(self.src / "Fantome.epub", CHAPITRE, "Fantôme")
        self.mapping["md/Rayon/Fantome.md"] = "D"                                   # la clé existe, pas le fichier
        avant = self.arbre()
        message = self.erreur("--redo-figures", "Fantome")
        self.assertIn("clé de MAPPING vers un fichier absent pour Fantome.epub : md/Rayon/Fantome.md", message)
        self.assertEqual(self.arbre(), avant)
        self.assertFalse(self.images.exists())

    def test_deux_sources_vers_le_meme_markdown_arretent(self):
        epub_images(self.src / "Cfd Éxact.epub", CHAPITRE, "Autre")                 # accent seul : pas le même nom pour le nom
        self.mapping[f"md/{ANCIEN}/Cfd Exact.md"] = "D"
        self.ecrire(f"{ANCIEN}/Cfd Exact.md", "ANCIEN EXACT")
        epub_images(self.src / "Cfd Exact.epub", CHAPITRE, "Exact")                 # trouvé par son nom
        avant = self.arbre()
        message = self.erreur("--redo-figures", "Cfd Exact", "Cfd Éxact")
        self.assertIn(f"deux livres vers le même Markdown {ANCIEN}/Cfd Exact.md", message)
        self.assertIn("Cfd Exact.epub", message)
        self.assertIn("Cfd Éxact.epub", message)
        self.assertEqual(self.arbre(), avant)

    def test_toutes_les_erreurs_sont_listees(self):
        epub_images(self.src / "Fantome.epub", CHAPITRE, "Fantôme")
        epub_images(self.src / "Sans cle.epub", CHAPITRE, "Sans clé")
        self.mapping["md/Rayon/Fantome.md"] = "D"
        message = self.erreur("--redo-figures", "Fantome", "Sans cle", ISBN)
        self.assertIn("clé de MAPPING vers un fichier absent pour Fantome.epub", message)
        self.assertIn("Markdown introuvable : Sans cle.epub", message)


class Simulation(FixtureMapping):
    """--dry-run : résout et affiche, sans rien convertir ni écrire."""

    def setUp(self):
        super().setUp()
        (self.src / "casse.epub").write_bytes(b"ceci n'est pas un epub")           # jamais ouvert en simulation
        self.ecrire("casse.md", "ANCIEN CASSE")
        self.avant = self.arbre()

    def simuler(self, *livres) -> tuple[str, int | None]:
        code = None
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["convert_books.py", str(self.src), str(self.dst),
                                             "--redo-figures", *livres, "--dry-run"]), \
                contextlib.redirect_stdout(sortie):
            try:
                cb.main()
            except SystemExit as erreur:
                code = erreur.code
        return sortie.getvalue(), code

    def test_affiche_source_markdown_et_voie_sans_rien_ecrire(self):
        sortie, code = self.simuler("cfd", ISBN, "casse")
        self.assertIsNone(code)
        self.assertIn(f"{NUMEROTE}/cfd.epub -> {ANCIEN}/cfd.md  (voie : nom)", sortie)
        self.assertIn(f"{NUMEROTE}/{ISBN}.epub -> Team Topologies - Skelton.md  "
                      "(voie : MAPPING, clé « md/Team Topologies - Skelton.md »)", sortie)
        self.assertIn("casse.epub -> casse.md  (voie : nom)", sortie)
        self.assertIn("Résolus : 3 (par correspondance explicite : 0, par nom : 2, par MAPPING : 1) · erreurs : 0", sortie)
        self.assertEqual(self.arbre(), self.avant)                                   # ni Markdown, ni sauvegarde, ni rapport
        self.assertFalse(self.images.exists())                                       # aucune image
        self.assertEqual((self.dst / ANCIEN / "cfd.md").read_text(encoding="utf-8"), "ANCIEN CFD")

    def test_toutes_les_erreurs_et_code_de_sortie(self):
        epub_images(self.src / "Fantome.epub", CHAPITRE, "Fantôme")
        epub_images(self.src / "Sans cle.epub", CHAPITRE, "Sans clé")
        self.mapping["md/Rayon/Fantome.md"] = "D"
        sortie, code = self.simuler("cfd", "Fantome", "Sans cle", "inconnu", ISBN)
        self.assertEqual(code, 1)
        self.assertIn("Erreurs de correspondance (3)", sortie)                      # les trois, pas la première seulement
        self.assertIn("introuvable : inconnu", sortie)
        self.assertIn("clé de MAPPING vers un fichier absent pour Fantome.epub", sortie)
        self.assertIn("Markdown introuvable : Sans cle.epub", sortie)
        self.assertIn(f"{NUMEROTE}/cfd.epub -> {ANCIEN}/cfd.md  (voie : nom)", sortie)   # les livres résolus s'affichent aussi
        self.assertEqual(self.arbre(), self.avant)
        self.assertFalse(self.images.exists())

    def test_dossier_de_sortie_absent(self):
        shutil.rmtree(self.dst)
        sortie, code = self.simuler("cfd")
        self.assertNotEqual(code, None)
        self.assertFalse(self.dst.exists())                                          # le dossier n'est pas créé


class ConversionNormaleParRecherche(FixtureMapping):
    """Option A : la conversion normale retrouve le Markdown existant de chaque livre (SOURCES, nom, MAPPING) et le
    réécrit sur place ; un livre sans Markdown est listé, non converti. --dry-run ne touche à rien."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(cb, "SOURCES", {f"{NUMEROTE}/cfd.epub": "md/Books/Nom sans rapport.md"})
        patch.start()
        self.addCleanup(patch.stop)
        self.ecrire("Books/Nom sans rapport.md", "ANCIEN EXPLICITE")
        epub_images(self.src / "Livre neuf.epub", CHAPITRE, "Neuf")                 # aucun Markdown, aucune clé
        self.avant = self.arbre()

    def test_les_trois_voies_et_le_livre_sans_markdown(self):
        sortie = self.lancer(preparer=False)
        for chemin in ("Books/Nom sans rapport.md", "Team Topologies - Skelton.md"):   # explicite, MAPPING
            self.assertIn("<!-- figure", (self.dst / chemin).read_text(encoding="utf-8"), chemin)
        self.assertEqual((self.dst / ANCIEN / "cfd.md").read_text(encoding="utf-8"), "ANCIEN CFD")   # SOURCES a pris cfd
        self.assertIn(f"{NUMEROTE}/cfd.epub -> Books/Nom sans rapport.md  (voie : correspondance explicite", sortie)
        self.assertIn(f"{NUMEROTE}/{ISBN}.epub -> Team Topologies - Skelton.md  (voie : MAPPING", sortie)
        self.assertIn("Sans Markdown existant, non convertis (1), à traiter avec --convert-book :\n  Livre neuf.epub",
                      sortie)
        self.assertFalse((self.dst / "Livre neuf.md").exists())                       # jamais créé
        self.assertFalse((self.dst / NUMEROTE).exists())
        self.assertEqual(sorted(p.name for p in self.images.iterdir()), ["9781942788829", "cfd"])   # pas « Livre neuf »
        rapport = (self.dst / "_rapport_conversion.txt").read_text(encoding="utf-8")
        self.assertIn("Convertis : 2", rapport)
        self.assertIn("Sans Markdown existant (non convertis) : 1", rapport)
        self.assertIn("(voie : correspondance explicite", rapport)

    def test_plusieurs_markdown_arretent_avant_toute_conversion(self):
        self.ecrire(f"{NUMEROTE}/Livre neuf.md", "UN")
        self.ecrire("Autre/Livre neuf.md", "DEUX")
        avant = self.arbre()
        with self.assertRaises(SystemExit) as erreur:
            self.lancer(preparer=False)
        message = str(erreur.exception.code)
        self.assertIn("conversion normale : rien n'a été converti", message)
        self.assertIn("plusieurs Markdown pour Livre neuf.epub", message)
        self.assertEqual(self.arbre(), avant)
        self.assertFalse(self.images.exists())

    def test_cle_vers_un_fichier_absent_et_deux_livres_vers_le_meme_markdown_arretent(self):
        (self.dst / "Books" / "Nom sans rapport.md").unlink()
        with self.assertRaises(SystemExit) as erreur:
            self.lancer(preparer=False)
        self.assertIn("correspondance explicite vers un Markdown absent pour", str(erreur.exception.code))
        self.ecrire("Books/Nom sans rapport.md", "ANCIEN EXPLICITE")
        cb.SOURCES[f"{NUMEROTE}/{ISBN}.epub"] = "md/Books/Nom sans rapport.md"        # deux sources, un Markdown
        with self.assertRaises(SystemExit) as erreur:
            self.lancer(preparer=False)
        self.assertIn("deux livres vers le même Markdown Books/Nom sans rapport.md", str(erreur.exception.code))
        self.assertFalse(self.images.exists())

    def simuler(self) -> tuple[str, int | None]:
        sortie, code = io.StringIO(), None
        with mock.patch.object(sys, "argv", ["convert_books.py", str(self.src), str(self.dst), "--dry-run"]), \
                contextlib.redirect_stdout(sortie):
            try:
                cb.main()
            except SystemExit as erreur:
                code = erreur.code
        return sortie.getvalue(), code

    def test_simulation_resout_liste_et_n_ecrit_rien(self):
        sortie, code = self.simuler()
        self.assertIsNone(code)
        self.assertIn("--dry-run (conversion normale) : 3 livre(s)", sortie)
        self.assertIn(f"{NUMEROTE}/cfd.epub -> Books/Nom sans rapport.md  (voie : correspondance explicite", sortie)
        self.assertIn(f"{NUMEROTE}/{ISBN}.epub -> Team Topologies - Skelton.md  (voie : MAPPING", sortie)
        self.assertIn("Sans Markdown existant, non convertis (1), à traiter avec --convert-book :\n  Livre neuf.epub",
                      sortie)
        self.assertIn("Résolus : 2 (par correspondance explicite : 1, par nom : 0, par MAPPING : 1) · sans Markdown : 1 "
                      "· exclus : 0 · erreurs : 0", sortie)
        self.assertEqual(self.arbre(), self.avant)                                   # ni Markdown, ni sauvegarde, ni rapport
        self.assertFalse(self.images.exists())

    def test_simulation_affiche_toutes_les_erreurs(self):
        self.ecrire(f"{NUMEROTE}/Livre neuf.md", "UN")
        self.ecrire("Autre/Livre neuf.md", "DEUX")
        epub_images(self.src / "Fantome.epub", CHAPITRE, "Fantôme")
        self.mapping["md/Rayon/Fantome.md"] = "D"                                    # clé sans fichier
        sortie, code = self.simuler()
        self.assertEqual(code, 1)
        self.assertIn("Erreurs de correspondance (2)", sortie)
        self.assertIn("plusieurs Markdown pour Livre neuf.epub", sortie)
        self.assertIn("clé de MAPPING vers un fichier absent pour Fantome.epub", sortie)

    def test_simulation_sans_dossier_de_sortie(self):
        shutil.rmtree(self.dst)
        sortie, code = self.simuler()
        self.assertIn("dossier de sortie introuvable", str(code))
        self.assertFalse(self.dst.exists())


class CorrespondanceExplicite(FixtureMapping):
    """SOURCES : correspondance explicite source -> Markdown, avant la recherche par nom et par MAPPING."""

    def setUp(self):
        super().setUp()
        self.ecrire("Books/Nom sans rapport.md", "ANCIEN RENOMME")
        self.sources = {f"{NUMEROTE}/{ISBN}.epub": "md/Books/Nom sans rapport.md"}
        patch = mock.patch.object(cb, "SOURCES", self.sources)
        patch.start()
        self.addCleanup(patch.stop)

    def test_reecrit_le_markdown_designe_avec_la_voie_explicite(self):
        sortie = self.lancer("--redo-figures", ISBN)
        voie = "(voie : correspondance explicite, md/Books/Nom sans rapport.md)"
        self.assertIn(f"{NUMEROTE}/{ISBN}.epub -> Books/Nom sans rapport.md  {voie}", sortie)
        self.assertIn("<!-- figure", (self.dst / "Books" / "Nom sans rapport.md").read_text(encoding="utf-8"))
        self.assertEqual((self.dst / "Books" / "Nom sans rapport.md.avant-figures").read_text(encoding="utf-8"),
                         "ANCIEN RENOMME")
        self.assertEqual((self.dst / "Team Topologies - Skelton.md").read_text(encoding="utf-8"),
                         EN_TETE.format(source=f"{ISBN}.epub") + "ANCIEN TT")   # la voie MAPPING n'est pas consultée
        self.assertIn(f"-> Books/Nom sans rapport.md {voie}",
                      (self.dst / "_rapport_figures.txt").read_text(encoding="utf-8"))

    def test_l_emporte_sur_le_nom_de_fichier(self):
        self.sources[f"{NUMEROTE}/cfd.epub"] = "md/Books/Nom sans rapport.md"      # « cfd.md » existe pourtant
        sortie = self.lancer("--redo-figures", "cfd")
        self.assertIn(f"{NUMEROTE}/cfd.epub -> Books/Nom sans rapport.md  (voie : correspondance explicite", sortie)
        self.assertEqual((self.dst / ANCIEN / "cfd.md").read_text(encoding="utf-8"), "ANCIEN CFD")

    def test_cle_sans_casse_ni_accents_ni_nfd(self):
        self.sources.clear()
        self.sources[f"{NUMEROTE}/{ISBN}.EPUB".replace("é", "e\u0301").upper().replace("03 LEAN", "03 Lean")] = \
            "md/Books/Nom sans rapport.md"
        self.assertIn("correspondance explicite", self.lancer("--redo-figures", ISBN))

    def test_markdown_absent_arrete_avant_toute_conversion(self):
        (self.dst / "Books" / "Nom sans rapport.md").unlink()
        avant = self.arbre()
        message = self.erreur("--redo-figures", ISBN, "cfd")                  # « cfd » est valide : rien n'est fait non plus
        self.assertIn("rien n'a été converti", message)
        self.assertIn(f"correspondance explicite vers un Markdown absent pour {NUMEROTE}/{ISBN}.epub : "
                      "md/Books/Nom sans rapport.md", message)
        self.assertNotIn("Team Topologies - Skelton.md", message)                # pas de repli sur MAPPING
        self.assertEqual(self.arbre(), avant)
        self.assertFalse(self.images.exists())

    def test_cible_hors_du_dossier_de_sortie_est_une_erreur(self):
        self.sources[f"{NUMEROTE}/{ISBN}.epub"] = "autre/Books/Nom sans rapport.md"
        self.assertIn("Markdown absent", self.erreur("--redo-figures", ISBN))

    def test_deux_sources_vers_le_meme_markdown_arretent(self):
        self.sources[f"{NUMEROTE}/cfd.epub"] = "md/Books/Nom sans rapport.md"
        message = self.erreur("--redo-figures", ISBN, "cfd")
        self.assertIn("deux livres vers le même Markdown Books/Nom sans rapport.md", message)

    def test_simulation_dit_la_voie_et_ne_modifie_rien(self):
        avant = self.arbre()
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["convert_books.py", str(self.src), str(self.dst),
                                             "--redo-figures", ISBN, "cfd", "--dry-run"]), \
                contextlib.redirect_stdout(sortie):
            cb.main()
        self.assertIn(f"{NUMEROTE}/{ISBN}.epub -> Books/Nom sans rapport.md  (voie : correspondance explicite", sortie.getvalue())
        self.assertIn(f"{NUMEROTE}/cfd.epub -> {ANCIEN}/cfd.md  (voie : nom)", sortie.getvalue())
        self.assertIn("par correspondance explicite : 1, par nom : 1, par MAPPING : 0", sortie.getvalue())
        self.assertEqual(self.arbre(), avant)
        self.assertFalse(self.images.exists())


class ConvertirUnLivre(Base):
    """--convert-book <livre> --to <Markdown> : un livre jamais converti, rangé dans un ancien dossier."""

    VERS = "Books/Un livre neuf.md"

    def setUp(self):
        super().setUp()
        self.dst.mkdir()
        epub_images(self.src / "02 Coaching" / "Un livre neuf.epub", CHAPITRE, "Un livre neuf")
        epub_images(self.src / "02 Coaching" / "Déjà là.epub", CHAPITRE, "Déjà là")
        (self.dst / "Books").mkdir()
        (self.dst / "Books" / "Déjà là.md").write_text("ANCIEN DEJA LA", encoding="utf-8")
        self.mapping = {f"md/{self.VERS}": "F", "md/Books/Déjà là.md": "D"}
        patch = mock.patch.object(cb, "MAPPING", self.mapping)
        patch.start()
        self.addCleanup(patch.stop)

    def arbre(self) -> list[str]:
        return sorted(str(p.relative_to(self.dst)) for p in self.dst.rglob("*") if p.is_file())

    def convertir(self, livre="Un livre neuf", vers=None) -> str:
        return self.lancer("--convert-book", livre, "--to", vers or self.VERS)

    def refuse(self, livre="Un livre neuf", vers=None) -> str:
        avant = self.arbre()
        with self.assertRaises(SystemExit) as erreur:
            self.convertir(livre, vers)
        self.assertEqual(self.arbre(), avant)                                      # rien n'est écrit
        self.assertFalse(self.images.exists())                                     # aucune image
        message = str(erreur.exception.code)
        self.assertIn("rien n'a été converti", message)
        return message

    def test_convertit_ce_seul_livre_dans_l_ancien_dossier(self):
        sortie = self.convertir()
        self.assertIn("<!-- figure", (self.dst / "Books" / "Un livre neuf.md").read_text(encoding="utf-8"))
        self.assertEqual(self.arbre(), ["Books/Déjà là.md", "Books/Un livre neuf.md", "_rapport_livre.txt"])
        self.assertFalse((self.dst / "02 Coaching").exists())                        # aucun dossier au nouveau nom
        self.assertEqual((self.dst / "Books" / "Déjà là.md").read_text(encoding="utf-8"), "ANCIEN DEJA LA")
        self.assertEqual(sorted(p.name for p in self.images.iterdir()), ["Un livre neuf"])   # images de ce livre seul
        self.assertIn("02 Coaching/Un livre neuf.epub -> Books/Un livre neuf.md", sortie)
        self.assertIn("Blocs figure créés : 6", sortie)
        self.assertIn("À faire ensuite : sort_by_domain.py", sortie)

    def test_refuse_un_markdown_existant(self):
        self.mapping["md/Books/Déjà là.md"] = "D"
        message = self.refuse("Déjà là", "Books/Déjà là.md")
        self.assertIn("le Markdown existe déjà : Books/Déjà là.md", message)
        self.assertEqual((self.dst / "Books" / "Déjà là.md").read_text(encoding="utf-8"), "ANCIEN DEJA LA")

    def test_refuse_un_nom_de_fichier_deja_pris_ailleurs(self):
        (self.dst / "Autre").mkdir()
        (self.dst / "Autre" / "Un livre neuf.md").write_text("AILLEURS", encoding="utf-8")
        self.assertIn("un autre Markdown porte déjà ce nom de fichier : Autre/Un livre neuf.md", self.refuse())

    def test_refuse_un_chemin_qui_n_est_pas_une_cle_de_mapping(self):
        self.assertIn("n'est pas une clé de MAPPING", self.refuse(vers="Books/Autre nom.md"))

    def test_refuse_un_chemin_invalide(self):
        for vers in ("../Evasion.md", "Books/sans-extension", "/Books/x.txt", "Books//x.md"):
            self.assertIn("chemin de Markdown invalide", self.refuse(vers=vers), vers)

    def test_refuse_un_livre_inconnu_ou_ambigu(self):
        epub_images(self.src / "x" / "Doublon.epub", CHAPITRE, "D1")
        epub_images(self.src / "y" / "Doublon.epub", CHAPITRE, "D2")
        self.assertIn("introuvable : inconnu", self.refuse("inconnu"))
        self.assertIn("ambigu : Doublon", self.refuse("Doublon"))

    def test_options_manquantes(self):
        for arguments in (("--convert-book", "Un livre neuf"), ("--to", self.VERS), ("--convert-book",)):
            with self.assertRaises(SystemExit):
                self.lancer(*arguments)
        self.assertEqual(self.arbre(), ["Books/Déjà là.md"])

    def test_dossier_de_sortie_absent(self):
        shutil.rmtree(self.dst)
        with self.assertRaises(SystemExit):
            self.convertir()
        self.assertFalse(self.dst.exists())

    def test_echec_de_la_conversion_n_ecrit_rien(self):
        (self.src / "02 Coaching" / "Casse.epub").write_bytes(b"ceci n'est pas un epub")
        self.mapping["md/Books/Casse.md"] = "F"
        avant = self.arbre()
        with self.assertRaises(SystemExit) as erreur:
            self.convertir("Casse", "Books/Casse.md")
        self.assertIn("rien n'a été écrit", str(erreur.exception.code))
        self.assertEqual(self.arbre(), avant)


class Exclusions(FixtureMapping):
    """EXCLUSIONS : une source que la conversion normale ignore, avec sa raison (ex. une autre édition du livre)."""

    SOURCE = "02 Coaching/Gamestorming.Jouer pour innover.epub"
    RAISON = "édition française : une autre édition que le Markdown anglais"

    def setUp(self):
        super().setUp()
        epub_images(self.src / self.SOURCE, CHAPITRE, "Jouer pour innover")
        self.ecrire("Books/Gamestorming.md", "ANCIEN ANGLAIS")
        self.mapping["md/Books/Gamestorming.md"] = "FP"
        patch = mock.patch.object(cb, "EXCLUSIONS", {self.SOURCE.upper().replace("COACHING", "Coaching"): self.RAISON})
        patch.start()
        self.addCleanup(patch.stop)
        self.avant = self.arbre()

    def simuler(self, *livres) -> tuple[str, int | None]:
        sortie, code = io.StringIO(), None
        arguments = [str(self.src), str(self.dst), *(["--redo-figures", *livres] if livres else []), "--dry-run"]
        with mock.patch.object(sys, "argv", ["convert_books.py", *arguments]), contextlib.redirect_stdout(sortie):
            try:
                cb.main()
            except SystemExit as erreur:
                code = erreur.code
        return sortie.getvalue(), code

    def test_la_conversion_normale_ignore_la_source_exclue(self):
        sortie = self.lancer(preparer=False)
        self.assertEqual((self.dst / "Books" / "Gamestorming.md").read_text(encoding="utf-8"), "ANCIEN ANGLAIS")
        self.assertFalse((self.dst / "Books" / "Gamestorming.md.avant-figures").exists())    # le Markdown anglais n'est pas touché
        self.assertFalse(self.images.exists() and (self.images / "Gamestorming.Jouer pour innover").exists())
        self.assertIn(f"Exclus de la conversion normale (1) :\n  {self.SOURCE} : {self.RAISON}", sortie)
        self.assertNotIn("Sans Markdown existant, non convertis", sortie)            # exclu n'est pas « sans Markdown »
        rapport = (self.dst / "_rapport_conversion.txt").read_text(encoding="utf-8")
        self.assertIn("Exclus (EXCLUSIONS) : 1", rapport)
        self.assertIn(f"{self.SOURCE} : {self.RAISON}", rapport.split("== Exclus (source : raison) ==")[1])
        self.assertIn("Sans Markdown existant (non convertis) : 0", rapport)

    def test_simulation_liste_l_exclu_avec_sa_raison(self):
        sortie, code = self.simuler()
        self.assertIsNone(code)
        self.assertIn(f"Exclus de la conversion normale (1) :\n  {self.SOURCE} : {self.RAISON}", sortie)
        self.assertIn("sans Markdown : 0 · exclus : 1 · erreurs : 0", sortie)
        self.assertNotIn("Gamestorming.Jouer", sortie.split("Exclus de la conversion normale")[0])   # pas résolu ailleurs
        self.assertEqual(self.arbre(), self.avant)

    def test_refaire_figures_refuse_un_livre_exclu_et_dit_la_raison(self):
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--redo-figures", "Gamestorming.Jouer pour innover")
        self.assertIn(f"livre exclu de la conversion : {self.SOURCE} ({self.RAISON})", str(erreur.exception.code))
        self.assertEqual(self.arbre(), self.avant)
        sortie, code = self.simuler("Gamestorming.Jouer pour innover")
        self.assertEqual(code, 1)
        self.assertIn("livre exclu de la conversion", sortie)

    def test_sans_exclusion_la_source_est_liee_par_le_nom_ou_listee(self):
        with mock.patch.object(cb, "EXCLUSIONS", {}):
            sortie = self.lancer(preparer=False)
        self.assertIn("Sans Markdown existant, non convertis (1)", sortie)                # sans la liste, elle serait listée


class TableCommune(unittest.TestCase):
    def test_une_seule_table_pour_la_conversion_et_la_ventilation(self):
        import mapping_lab
        import sort_by_domain
        self.assertIs(cb.MAPPING, mapping_lab.MAPPING)
        self.assertIs(sort_by_domain.MAPPING, mapping_lab.MAPPING)
        self.assertIs(sort_by_domain.DOMAINS, mapping_lab.DOMAINS)

    def test_fold_sans_casse_ni_accents(self):
        import mapping_lab
        self.assertEqual(mapping_lab.fold("Équipes Autonomes "), mapping_lab.fold("equipes AUTONOMES"))
        self.assertEqual(mapping_lab.norm("e\u0301"), "\u00e9")


class StatistiquesAvantReconversion(Base):
    def test_colonne_et_raisons_des_textes_alternatifs_inutiles(self):
        alts = ['<p><img src="a.png" alt="image"/></p>' * 1, '<p><img src="b.png" alt="IMG_0001.png"/></p>',
                '<p><img src="c.png" alt="Logo"/></p>', '<p><img src="d.png" alt="Courbe du lead time"/></p>',
                '<p><img src="e.png" alt="Description de l\'image du livre"/></p>' * 3]
        epub_images(self.src / "alts.epub", "".join(alts), "Alts")
        stats = cb.figure_stats_epub(self.src / "alts.epub")
        self.assertEqual(stats["visuels"], 7)
        self.assertEqual((stats["alt"], stats["alt_utiles"], stats["alt_inutiles"]), (7, 4, 3))
        self.assertEqual(stats["raisons"], {"générique": 2, "fichier": 1})   # « image », « Logo » ; « IMG_0001.png »
        self.assertEqual(stats["alt_repetes"], 3)             # trois alt identiques sans légende : information seulement
        self.assertEqual(stats["exploitables"], 4)            # ces trois répétés restent retenus (pas de filtre de répétition)

    def test_les_statistiques_et_la_conversion_retiennent_les_memes_figures(self):
        epub_images(self.src / "figures.epub", CHAPITRE, "Livre à figures")
        retenues = cb.figure_stats_epub(self.src / "figures.epub")["exploitables"]
        self.lancer()
        self.assertEqual(self.md("figures").count("<!-- figure"), retenues)
        figures.pdf_figures(self.src / "schemas.pdf")
        retenues = cb.figure_stats_pdf(self.src / "schemas.pdf")["exploitables"]
        self.lancer()
        self.assertEqual(self.md("schemas").count("<!-- figure"), retenues)

    def test_colonne_dans_le_tableau_et_notes(self):
        alts = "".join(f'<p><img src="a{n}.png" alt="image"/></p>' for n in range(12))
        epub_images(self.src / "beaucoup.epub", alts, "Beaucoup")
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["convert_books.py", "--figure-statistics", str(self.src),
                                             str(self.dst)]), contextlib.redirect_stdout(sortie), \
                contextlib.redirect_stderr(io.StringIO()):
            cb.main()
        texte = sortie.getvalue()
        self.assertIn("Alt inut.", texte)
        ligne = next(l for l in texte.splitlines() if l.startswith("beaucoup"))
        self.assertIn("alt inutiles : 12 générique", ligne)
        self.assertEqual(ligne.split()[1:10], ["EPUB", "12", "0", "0", "0", "12", "12", "0", "0"])
        self.assertIn("inutiles : 12 (fichier : 0 · générique : 12 · court : 0)", texte)


class Cadre(unittest.TestCase):
    def test_dossier_des_images_ignore_par_git_et_refuse_a_claude_code(self):
        gitignore = (RACINE / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/Bibliotheque-Images/", gitignore)
        deny = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"]
        self.assertIn("Read(./Bibliotheque-Images/**)", deny)
        self.assertIn("Read(**/Bibliotheque-Images/**)", deny)
        for commande in ("cat", "cp", "base64"):
            self.assertIn(f"Bash({commande} *Bibliotheque-Images*)", deny)

    def test_dossier_par_defaut_dans_le_workspace(self):
        self.assertEqual(cb.IMAGES_NAME, "Bibliotheque-Images")


if __name__ == "__main__":
    unittest.main()
