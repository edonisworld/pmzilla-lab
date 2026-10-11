"""
Tests de la conversion des livres (tools/convert_books.py) sur des EPUB et des PDF minuscules inventés.

    uv run --with pymupdf4llm --with ebooklib --with markdownify --with beautifulsoup4 \
        python -m unittest discover -s tests/convert_books -v

Les livres sont fabriqués dans le test, dans un dossier temporaire : avec texte, presque vides, scannés (pages
sans texte) et corrompus. Aucun vrai livre n'est lu, rien n'est écrit hors du dossier temporaire.
"""
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import convert_books as cb  # noqa: E402

PHRASE = "Le flux de valeur relie la discovery à la livraison et rend la prévision plus fiable. "


def pdf(path: Path, pages: int, texte: str = "") -> None:
    import pymupdf
    document = pymupdf.open()
    for numero in range(pages):
        page = document.new_page()
        if texte:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 780), f"Page {numero + 1}. {texte}", fontsize=11)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(path))
    document.close()


def epub(path: Path, titre: str, chapitres: list[tuple[str, str]]) -> None:
    """chapitres : (titre dans la table des matières, HTML du corps)."""
    from ebooklib import epub as lib
    livre = lib.EpubBook()
    livre.set_identifier("id-" + path.stem)
    livre.set_title(titre)
    livre.set_language("fr")
    items = []
    for numero, (toc, html) in enumerate(chapitres, 1):
        chapitre = lib.EpubHtml(title=toc, file_name=f"chap{numero}.xhtml", lang="fr")
        chapitre.content = f"<html><body>{html}</body></html>"
        livre.add_item(chapitre)
        items.append(chapitre)
    livre.toc = tuple(items)
    livre.add_item(lib.EpubNcx())
    livre.add_item(lib.EpubNav())
    livre.spine = ["nav", *items]
    path.parent.mkdir(parents=True, exist_ok=True)
    lib.write_epub(str(path), livre)


def long(n: int = 40) -> str:
    return "".join(f"<p>{PHRASE}Variante {i}.</p>" for i in range(n))


class Base(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = self.tmp / "livres"
        self.dst = self.tmp / "markdown"
        self.images = self.tmp / "images"
        self.src.mkdir()
        patch = mock.patch.object(cb, "IMAGES_DIR", self.images)   # jamais le vrai Bibliotheque-Images
        patch.start()
        self.addCleanup(patch.stop)

    def preparer(self) -> None:
        """La conversion normale réécrit le Markdown existant de chaque livre : un Markdown « ANCIEN » est posé, au
        chemin de la source, pour chaque livre qui n'en a pas encore (l'EPUB l'emporte sur le PDF du même nom)."""
        livres = sorted(p for p in self.src.rglob("*") if p.suffix.lower() in (".pdf", ".epub"))
        for livre in cb.preferred_books(livres, self.src):
            md = self.dst / livre.relative_to(self.src).with_suffix(".md")
            if not md.exists():
                md.parent.mkdir(parents=True, exist_ok=True)
                md.write_text("ANCIEN", encoding="utf-8")

    def lancer(self, *arguments, preparer: bool = True) -> str:
        if not arguments and preparer:
            self.preparer()
        arguments = arguments or (str(self.src), str(self.dst))
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["convert_books.py", *arguments]), contextlib.redirect_stdout(sortie):
            cb.main()
        return sortie.getvalue()

    def rapport(self) -> str:
        return (self.dst / "_rapport_conversion.txt").read_text(encoding="utf-8")


class Formats(Base):
    def test_pdf_avec_texte(self):
        pdf(self.src / "texte.pdf", 2, PHRASE * 12)
        self.lancer()
        md = (self.dst / "texte.md").read_text(encoding="utf-8")
        self.assertTrue(md.startswith('---\ntitle: "texte"\nsource: "texte.pdf"\npages: 2\nfigures: 0\n---\n'))
        self.assertIn("discovery à la livraison", md)
        self.assertIn("Convertis : 1", self.rapport())
        self.assertIn("À vérifier : 0", self.rapport())

    def test_pdf_scanne_signale(self):
        pdf(self.src / "scan.pdf", 3)
        self.lancer()
        self.assertTrue((self.dst / "scan.md").exists())   # converti quand même, mais à vérifier
        rapport = self.rapport()
        self.assertIn("À vérifier : 1", rapport)
        self.assertIn("scan.pdf : PDF probablement scanné (", rapport)
        self.assertIn("pour 3 pages)", rapport)

    def test_epub_avec_texte_titres_et_table_des_matieres(self):
        epub(self.src / "livre.epub", 'Livre "inventé"', [
            ("Chapitre un", "<h1>Chapitre un</h1>" + long()),
            ("Chapitre deux de la table", long(10))])
        self.lancer()
        md = (self.dst / "livre.md").read_text(encoding="utf-8")
        self.assertTrue(md.startswith("---\ntitle: \"Livre 'inventé'\"\nsource: \"livre.epub\"\nfigures: 0\n---\n"))
        self.assertNotIn("pages:", md)
        self.assertIn("# Chapitre un", md)
        self.assertIn("# Chapitre deux de la table", md)   # chapitre sans balise de titre : titre pris dans la table
        self.assertEqual(md.count("# Chapitre un"), 1)
        self.assertIn("À vérifier : 0", self.rapport())

    def test_epub_presque_vide_signale(self):
        epub(self.src / "drm.epub", "Protégé", [("Seul", "<p>Texte minuscule.</p>")])
        self.lancer()
        self.assertIn("drm.epub : EPUB presque vide (", self.rapport())

    def test_titre_de_repli_sur_le_nom_du_fichier(self):
        epub(self.src / "sans-titre.epub", " ", [("C", long())])
        self.lancer()
        self.assertIn('title: "sans-titre"', (self.dst / "sans-titre.md").read_text(encoding="utf-8"))

    def test_fichiers_corrompus_ne_bloquent_pas_les_autres(self):
        (self.src / "casse.pdf").write_bytes(b"ceci n'est pas un pdf")
        (self.src / "autre-casse.epub").write_bytes(b"ceci n'est pas un epub")
        (self.src / "vide.pdf").write_bytes(b"")
        pdf(self.src / "bon.pdf", 1, PHRASE * 12)
        sortie = self.lancer()
        self.assertIn("discovery à la livraison", (self.dst / "bon.md").read_text(encoding="utf-8"))
        self.assertEqual((self.dst / "casse.md").read_text(encoding="utf-8"), "ANCIEN")   # en erreur : l'ancien reste
        self.assertEqual((self.dst / "vide.md").read_text(encoding="utf-8"), "ANCIEN")
        rapport = self.rapport()
        self.assertIn("Convertis : 1", rapport)
        self.assertIn("Erreurs : 3", rapport)
        self.assertIn("autre-casse.epub : ", rapport)
        self.assertIn("ERREUR", sortie)
        # un fichier en erreur n'écrit rien : il sera retenté au prochain passage
        pdf(self.src / "casse.pdf", 1, PHRASE * 12)
        self.lancer()
        self.assertIn("discovery à la livraison", (self.dst / "casse.md").read_text(encoding="utf-8"))

    def test_epub_corrompu_repli_sur_le_pdf_et_rapport(self):
        """Un EPUB qui échoue à la conversion : le PDF du même livre est converti à sa place et le rapport le dit."""
        (self.src / "livre.epub").write_bytes(b"ceci n'est pas un epub")
        pdf(self.src / "livre.pdf", 1, PHRASE * 12)
        sortie = self.lancer()
        md = (self.dst / "livre.md").read_text(encoding="utf-8")
        self.assertIn('source: "livre.pdf"', md)
        self.assertIn("discovery à la livraison", md)
        rapport = self.rapport()
        self.assertIn("Convertis : 1", rapport)
        self.assertIn("Repli sur le PDF (EPUB en échec) : 1", rapport)
        self.assertIn("PDF ignorés car l'EPUB existe : 0", rapport)    # ce PDF n'est plus « ignoré »
        self.assertIn("Erreurs : 0", rapport)
        repli = rapport.split("== Repli sur le PDF (l'EPUB n'a pas pu être converti) ==")[1].split("==")[0]
        self.assertIn("livre.epub : EPUB en échec (", repli)
        self.assertIn("converti depuis livre.pdf", repli)
        self.assertIn("repli sur livre.pdf", sortie)
        self.assertIn("Repli sur le PDF (EPUB en échec) : 1", sortie)   # visible aussi dans la sortie du terminal

    def test_repli_est_reecrit_a_chaque_passage_avec_l_ancien_garde_une_fois(self):
        (self.src / "livre.epub").write_bytes(b"ceci n'est pas un epub")
        pdf(self.src / "livre.pdf", 1, PHRASE * 12)
        self.lancer()
        self.assertEqual((self.dst / "livre.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN")
        (self.dst / "livre.md").write_text("MODIFIÉ À LA MAIN", encoding="utf-8")
        self.lancer()
        self.assertIn("discovery à la livraison", (self.dst / "livre.md").read_text(encoding="utf-8"))   # réécrit
        self.assertEqual((self.dst / "livre.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN")    # une seule fois
        self.assertIn("déjà là d'un passage précédent : 1", self.rapport())

    def test_epub_et_pdf_en_echec_sont_deux_erreurs(self):
        (self.src / "livre.epub").write_bytes(b"ceci n'est pas un epub")
        (self.src / "livre.pdf").write_bytes(b"ceci n'est pas un pdf")
        self.lancer()
        rapport = self.rapport()
        self.assertEqual((self.dst / "livre.md").read_text(encoding="utf-8"), "ANCIEN")
        self.assertIn("Erreurs : 2", rapport)
        self.assertIn("Repli sur le PDF (EPUB en échec) : 0", rapport)
        self.assertIn("livre.pdf : ", rapport.split("== Erreurs ==")[1])
        self.assertIn("repli après l'échec de l'EPUB", rapport)

    def test_repli_sur_un_pdf_scanne_est_a_verifier(self):
        (self.src / "scan.epub").write_bytes(b"ceci n'est pas un epub")
        pdf(self.src / "scan.pdf", 3)
        self.lancer()
        self.assertIn("scan.pdf : PDF probablement scanné", self.rapport())

    def test_epub_corrompu_sans_pdf_reste_une_erreur(self):
        (self.src / "seul.epub").write_bytes(b"ceci n'est pas un epub")
        self.lancer()
        self.assertIn("Erreurs : 1", self.rapport())
        self.assertEqual((self.dst / "seul.md").read_text(encoding="utf-8"), "ANCIEN")


class Selection(Base):
    def test_epub_prefere_au_pdf_meme_nom(self):
        epub(self.src / "Livre.epub", "Du livre", [("C", long())])
        pdf(self.src / "livre.pdf", 1, PHRASE * 12)           # même nom, casse différente
        pdf(self.src / "sous" / "autre.pdf", 1, PHRASE * 12)  # même nom dans un autre dossier : pas un doublon
        epub(self.src / "sous" / "autre-ebook.epub", "Autre", [("C", long())])
        self.lancer()
        rapport = self.rapport()
        self.assertIn("figures: 0", (self.dst / "Livre.md").read_text(encoding="utf-8"))   # EPUB réécrit sur place
        self.assertFalse((self.dst / "livre.md").exists() and "pages:" in (self.dst / "livre.md").read_text())
        self.assertIn("PDF ignorés car l'EPUB existe : 1", rapport)
        self.assertIn("livre.pdf", rapport.split("== PDF ignorés car l'EPUB existe ==")[1])
        self.assertIn("pages: 1", (self.dst / "sous" / "autre.md").read_text(encoding="utf-8"))

    def test_le_markdown_garde_son_emplacement_aucune_arborescence_recreee(self):
        pdf(self.src / "a" / "b" / "profond.pdf", 1, PHRASE * 12)
        (self.dst / "Rayon").mkdir(parents=True)
        (self.dst / "Rayon" / "profond.md").write_text("ANCIEN", encoding="utf-8")
        self.lancer(preparer=False)
        self.assertIn("discovery à la livraison", (self.dst / "Rayon" / "profond.md").read_text(encoding="utf-8"))
        self.assertFalse((self.dst / "a").exists())                 # le dossier de la source n'a aucune influence

    def test_tout_est_reecrit_a_chaque_passage_ancien_garde_une_seule_fois(self):
        pdf(self.src / "un.pdf", 1, PHRASE * 12)
        pdf(self.src / "deux.pdf", 1, PHRASE * 12)
        self.lancer()
        (self.dst / "un.md").write_text("MODIFIÉ À LA MAIN", encoding="utf-8")
        sortie = self.lancer()
        self.assertIn("discovery à la livraison", (self.dst / "un.md").read_text(encoding="utf-8"))
        self.assertEqual((self.dst / "un.md.avant-figures").read_text(encoding="utf-8"), "ANCIEN")
        self.assertIn("Convertis : 2", self.rapport())
        self.assertIn("[2/2]", sortie)

    def test_livre_sans_markdown_est_liste_et_non_converti(self):
        pdf(self.src / "avec.pdf", 1, PHRASE * 12)
        pdf(self.src / "dossier" / "sans.pdf", 1, PHRASE * 12)
        (self.dst).mkdir()
        (self.dst / "avec.md").write_text("ANCIEN", encoding="utf-8")
        sortie = self.lancer(preparer=False)
        self.assertEqual(sorted(p.name for p in self.dst.rglob("*") if p.is_file()),
                         ["_rapport_conversion.txt", "avec.md", "avec.md.avant-figures"])   # rien pour « sans »
        self.assertFalse((self.dst / "dossier").exists())
        self.assertIn("Sans Markdown existant, non convertis (1), à traiter avec --convert-book :", sortie)
        self.assertIn("  dossier/sans.pdf", sortie)
        rapport = self.rapport()
        self.assertIn("Sans Markdown existant (non convertis) : 1", rapport)
        self.assertIn("dossier/sans.pdf", rapport.split("== Sans Markdown existant")[1].split("==")[1])
        self.assertIn("Convertis : 1", rapport)
        self.assertFalse(self.images.exists() and (self.images / "sans").exists())

    def test_extensions_en_majuscules_et_autres_fichiers(self):
        pdf(self.src / "MAJ.PDF", 1, PHRASE * 12)
        (self.src / "notes.txt").write_text("pas un livre")
        sortie = self.lancer()
        self.assertIn("1 livres trouvés", sortie)
        self.assertIn("discovery à la livraison", (self.dst / "MAJ.md").read_text(encoding="utf-8"))

    def test_arguments_et_dossier_absent(self):
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("seul-argument")
        self.assertEqual(erreur.exception.code, 1)
        with self.assertRaises(SystemExit):
            self.lancer(str(self.tmp / "absent"), str(self.dst))

    def test_dossier_vide(self):
        sortie = self.lancer()
        self.assertIn("0 livres trouvés", sortie)
        self.assertIn("Convertis : 0", self.rapport())


if __name__ == "__main__":
    unittest.main()
