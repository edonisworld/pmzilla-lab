"""
Tests des figures dans la bibliothèque (tools/pmzilla_lab_library.py) : passages de type
figure, légende PDF sans doublon, paramètre `types` de la recherche, `ref` et chemin de l'image en texte,
aucun accès aux images.

    uv run --with numpy --with httpx --with pyyaml --with pymupdf4llm --with ebooklib --with markdownify \
        --with beautifulsoup4 python -m unittest discover -s tests/pmzilla_lab_library -v

Livres Markdown inventés dans un dossier temporaire ; l'embedding d'Ollama est remplacé par un plongement
déterministe ; l'indexeur écrit dans un faux magasin en mémoire (fake_store.FakeStore) ; les tests de recherche par
`types` (classe Types) indexent dans une base jetable et lisent par PostgresLibrary (sautés sans base, lancés par
tools/dbtest.sh). Jamais Bibliotheque-MD, Bibliotheque-Images, le vrai index ni la vraie base. (Le test d'intégration sur un vrai PDF
fabriqué est ignoré quand PyMuPDF n'est pas installé.)
"""
import ast
import builtins
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pmzilla_lab_library as library  # noqa: E402
from fake_store import FakeStore  # noqa: E402
import knowledge_library  # noqa: E402
from test_pmzilla_lab_library import fake_embed, fake_embed_1024  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]

TEXTE = ("Un paragraphe de texte courant assez long pour former un passage : le flux, la limite de travail en "
         "cours, le délai de livraison et la prévision, expliqués avec soin pour dépasser le seuil de longueur. ")

LIVRE_PDF = f"""---
title: "Livre PDF inventé"
source: "pdf-livre.pdf"
pages: 4
figures: 2
---

# Partie un

## Le flux

{TEXTE}Le tableau de la Figure 1.1 montre les trois colonnes d'un tableau kanban et la limite de travail. Autre phrase.

**Figure 1.1** Un tableau kanban inventé

{TEXTE}Suite du texte de la même page.

-----

<!-- figure id=fig-0001 source=pdf page=1 image="Bibliotheque-Images/pdf-livre/fig-0001.png" -->
Légende : Figure 1.1 Un tableau kanban inventé

## Les limites

{TEXTE}Un second paragraphe de la page trois.
Fig. 2.1 Courbe du délai de livraison inventée
{TEXTE}Encore du texte.

<!-- figure id=fig-0002 source=pdf page=3 image="Bibliotheque-Images/pdf-livre/fig-0002.png" -->
Légende : Fig. 2.1 Courbe du délai de livraison inventée

{TEXTE}Fin du livre.
"""

LIVRE_EPUB = f"""---
title: "Livre EPUB inventé"
source: "epub-livre.epub"
figures: 2
---

# Les équipes

{TEXTE}Voir la Figure 3.2 pour les interactions entre équipes. Elles se choisissent.

<!-- figure id=fig-0001 source=epub image="Bibliotheque-Images/epub-livre/fig-0001.png" -->
Légende : Figure 3.2 Les interactions entre équipes
Texte alternatif : Trois équipes reliées par des flèches de collaboration

<!-- figure id=fig-0002 source=epub -->
Texte alternatif : Courbe montrant le lead time par semaine

{TEXTE}Un dernier paragraphe, après les figures.
"""

LIVRE_TEXTE = f"# Texte seul\n\n## Section\n\n{TEXTE}Du kanban encore.\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.racine = self.tmp / "collections"
        self.embedded: list[str] = []
        self.calls = 0
        self.store = FakeStore()

        def embed(texts):
            self.calls += 1
            self.embedded += list(texts)
            return fake_embed(texts)

        for patch in (
            mock.patch.object(library, "CATALOGUE_PATH", self.tmp / "catalogue.yaml"),
            mock.patch.object(library, "embed", embed),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def ecrire(self, relatif: str, texte: str) -> Path:
        chemin = self.racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def indexer(self) -> str:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            library.index([self.racine], store=self.store)
        return sortie.getvalue()

    def chunks(self, fichier: str | None = None, kind: str | None = None) -> list[dict]:
        """Passages stockés (faux magasin), dans l'ordre du fichier puis de la position ; `ref` en JSON trié, comme en base."""
        return [dict(p, file_name=nom, ref=json.dumps(p["ref"], ensure_ascii=False, sort_keys=True))
                for nom, b in sorted(self.store.books.items()) if fichier in (None, nom)
                for p in sorted(b["passages"], key=lambda p: p["position"]) if kind in (None, p["kind"])]


class Livres(Base):
    def setUp(self):
        super().setUp()
        self.ecrire_livres()
        self.sortie = self.indexer()

    def ecrire_livres(self):
        self.ecrire("flow/pdf-livre.md", LIVRE_PDF)
        self.ecrire("organisation/epub-livre.md", LIVRE_EPUB)
        self.ecrire("flow/texte.md", LIVRE_TEXTE)


class PassagesFigure(Livres):
    def test_le_commentaire_n_est_jamais_du_texte_courant(self):
        for ligne in self.chunks(kind="text"):
            for interdit in ("<!--", "-->", "figure id=", "Bibliotheque-Images", "Légende :", "Texte alternatif :"):
                self.assertNotIn(interdit, ligne["text"], interdit)

    def test_commentaire_mal_forme_ou_colle_au_texte(self):
        passages = library.split_passages(
            f"# T\n\n{TEXTE}\n<!-- figure id=fig-0009 source=pdf\n{TEXTE}Suite.\n"
            f"<!-- figure id=fig-0010 source=epub -->\nLégende : Figure 9 Une légende\nSuite collée au bloc. {TEXTE}\n")
        textes = [p.text for p in passages if p.kind == "texte"]
        figures = [p for p in passages if p.kind == "figure"]
        self.assertTrue(all("<!--" not in t and "figure id" not in t for t in textes))
        self.assertEqual([p.ref["id"] for p in figures], ["fig-0010"])        # le commentaire non fermé est écarté
        self.assertIn("Suite collée au bloc.", " ".join(textes))               # la ligne qui suit le bloc reste du texte

    def test_un_bloc_est_un_passage_a_part_a_sa_place(self):
        pdf = self.chunks("pdf-livre.md")
        self.assertEqual([r["kind"] for r in pdf], ["text", "figure", "text", "figure", "text"])
        self.assertEqual([r["position"] for r in pdf], list(range(len(pdf))))
        self.assertEqual([r["section"] for r in pdf if r["kind"] == "figure"],
                         ["Partie un > Le flux", "Partie un > Les limites"])
        self.assertEqual(len(self.chunks("epub-livre.md", "figure")), 2)
        self.assertEqual(len(self.chunks("texte.md", "figure")), 0)
        self.assertIn("dont 2 figures", self.sortie)

    def test_texte_vectorise_legende_alt_utile_et_phrase_de_renvoi(self):
        figure = next(r for r in self.chunks("pdf-livre.md", "figure"))
        self.assertEqual(figure["text"], "Figure 1.1 Un tableau kanban inventé\nDans le texte : "
                         "Le tableau de la Figure 1.1 montre les trois colonnes d'un tableau kanban et la limite de "
                         "travail.")
        epub = self.chunks("epub-livre.md", "figure")
        self.assertEqual(epub[0]["text"],
                         "Figure 3.2 Les interactions entre équipes\n"
                         "Texte alternatif : Trois équipes reliées par des flèches de collaboration\n"
                         "Dans le texte : Voir la Figure 3.2 pour les interactions entre équipes.")
        self.assertEqual(epub[1]["text"], "Texte alternatif : Courbe montrant le lead time par semaine")  # pas de renvoi
        vectorise = [t for t in self.embedded if "Un tableau kanban inventé" in t]
        self.assertEqual(len(vectorise), 1)
        self.assertTrue(vectorise[0].startswith("Livre PDF inventé\nPartie un > Le flux\nFigure 1.1 Un tableau"))
        for texte in self.embedded:   # ni commentaire, ni chemin d'image dans ce qui est vectorisé
            self.assertNotIn("<!--", texte)
            self.assertNotIn("Bibliotheque-Images", texte)

    def test_ref(self):
        pdf = [json.loads(r["ref"]) for r in self.chunks("pdf-livre.md", "figure")]
        self.assertEqual(pdf[0], {"id": "fig-0001", "label": "Figure 1.1", "page": 1, "section": "Partie un > Le flux",
                                  "legende": "Figure 1.1 Un tableau kanban inventé",
                                  "image": "Bibliotheque-Images/pdf-livre/fig-0001.png", "source": "pdf"})
        self.assertEqual(pdf[1]["label"], "Fig. 2.1")
        self.assertEqual(pdf[1]["page"], 3)
        epub = [json.loads(r["ref"]) for r in self.chunks("epub-livre.md", "figure")]
        self.assertEqual(epub[1], {"id": "fig-0002", "section": "Les équipes", "source": "epub",   # alt seul : ni libellé, ni page, ni image
                                   "texte_alternatif": "Courbe montrant le lead time par semaine"})
        for r in self.chunks(kind="text"):
            self.assertEqual(r["ref"], "{}")

    def test_origine_du_texte_legende_et_texte_alternatif_chacun_dans_son_champ(self):
        pdf = [json.loads(r["ref"]) for r in self.chunks("pdf-livre.md", "figure")]
        epub = [json.loads(r["ref"]) for r in self.chunks("epub-livre.md", "figure")]
        for ref in pdf:                                  # PDF : une légende, jamais de texte alternatif
            self.assertIn("legende", ref)
            self.assertNotIn("texte_alternatif", ref)
        self.assertEqual(epub[0]["legende"], "Figure 3.2 Les interactions entre équipes")          # les deux, séparés
        self.assertEqual(epub[0]["texte_alternatif"], "Trois équipes reliées par des flèches de collaboration")
        self.assertNotIn("legende", epub[1])                                                       # alt seul
        self.assertEqual(epub[1]["texte_alternatif"], "Courbe montrant le lead time par semaine")

    def test_alt_identique_a_la_legende_n_est_pas_un_texte_alternatif(self):
        passages = library.split_passages(
            f"# T\n\n{TEXTE}\n<!-- figure id=fig-0001 source=epub -->\nLégende : Figure 4 Un schéma\n"
            "Texte alternatif : Figure 4 Un schéma\n")
        ref = next(p.ref for p in passages if p.kind == "figure")
        self.assertEqual(ref["legende"], "Figure 4 Un schéma")
        self.assertNotIn("texte_alternatif", ref)

    def test_section_toujours_remplie_pour_les_figures_epub_et_pdf(self):
        lignes = self.chunks(kind="figure")
        self.assertEqual({r["file_name"] for r in lignes}, {"pdf-livre.md", "epub-livre.md"})
        for ligne in lignes:
            section = json.loads(ligne["ref"]).get("section")
            self.assertTrue(section, ligne["file_name"])
            self.assertEqual(section, ligne["section"])            # la même que celle du passage

    def test_section_d_une_figure_avant_tout_titre(self):
        for source in ("epub", "pdf"):
            passages = library.split_passages(
                f"<!-- figure id=fig-0001 source={source} -->\nLégende : Figure 1 Un schéma\n\n# Titre\n\n{TEXTE}\n")
            self.assertEqual(next(p.ref["section"] for p in passages if p.kind == "figure"), "(no heading)")

    def test_texte_inchange_pour_un_livre_sans_figure(self):
        avant = library.split_passages(LIVRE_TEXTE)
        self.assertEqual([p.kind for p in avant], ["texte"])
        self.assertIsNone(avant[0].ref)

    def test_relance_et_modification(self):
        appels = self.calls
        self.assertIn("unchanged: 3", self.indexer())
        self.assertEqual(self.calls, appels)                                   # rien n'est recalculé
        self.ecrire("flow/pdf-livre.md", LIVRE_PDF + "\nUn ajout en fin de livre, assez long pour former un passage "
                                                    "de texte courant à part entière, avec du vocabulaire distinct.\n")
        self.assertIn("Indexed: 1 · unchanged: 2", self.indexer())
        self.assertEqual(len(self.chunks("pdf-livre.md", "figure")), 2)       # remplacés, jamais dupliqués


class Recalcul(Livres):
    """index(..., force) et --recompute : recalcul de livres précis dont le Markdown n'a pas changé."""

    def avec_args(self, *args: str) -> str:
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["pmzilla_lab_library.py", "index", str(self.racine), *args]), \
                contextlib.redirect_stdout(sortie):
            library.main(store=self.store)
        return sortie.getvalue()

    def test_sans_option_rien_n_est_recalcule(self):
        appels = self.calls
        self.assertIn("unchanged: 3", self.indexer())
        self.assertEqual(self.calls, appels)

    def test_un_livre_designe_par_son_nom_est_recalcule_seul(self):
        appels = self.calls
        sortie = self.avec_args("--recompute", "pdf-livre")
        self.assertIn("Indexed: 1 · unchanged: 2", sortie)
        self.assertGreater(self.calls, appels)
        self.assertEqual(len(self.chunks("pdf-livre.md", "figure")), 2)       # remplacés, jamais dupliqués

    def test_nom_avec_extension_chemin_et_casse(self):
        for designation in ("PDF-Livre.pdf", "flow/pdf-livre.md", "Quelque/Dossier/pdf-livre.epub"):
            self.assertIn("Indexed: 1 · unchanged: 2", self.avec_args("--recompute", designation), designation)

    def test_liste_dans_un_fichier(self):
        liste = self.tmp / "liste.txt"
        liste.write_text("# pilote\nepub-livre.epub\n\n  pdf-livre  \n", encoding="utf-8")
        self.assertIn("Indexed: 2 · unchanged: 1", self.avec_args("--recompute", f"@{liste}"))

    def test_ref_enrichi_apres_recalcul(self):
        for b in self.store.books.values():        # un index d'avant : le ref d'une figure sans origine
            for p in b["passages"]:
                if p["kind"] == "figure":
                    p["ref"] = {}
        self.assertIn("Indexed: 0", self.indexer())                             # sans l'option, il reste ancien
        self.assertEqual({r["ref"] for r in self.chunks(kind="figure")}, {"{}"})
        self.avec_args("--recompute", "pdf-livre", "epub-livre")
        for ligne in self.chunks(kind="figure"):
            ref = json.loads(ligne["ref"])
            self.assertTrue("legende" in ref or "texte_alternatif" in ref)

    def test_livre_inconnu_ou_ambigu_arrete_tout_sans_toucher_l_index(self):
        self.ecrire("organisation/Texte.md", LIVRE_TEXTE)             # même nom que texte.md, à la casse près
        self.indexer()
        avant = [(r["file_name"], r["position"], r["text"]) for r in self.chunks()]
        appels = self.calls
        for designation in ("inexistant", "texte.md"):
            with self.assertRaises(SystemExit) as erreur:
                self.avec_args("--recompute", "pdf-livre", designation)
            self.assertIn("nothing was indexed", str(erreur.exception))
            if designation == "texte.md":
                self.assertIn("ambiguous", str(erreur.exception))
        self.assertEqual(self.calls, appels)
        self.assertEqual([(r["file_name"], r["position"], r["text"]) for r in self.chunks()], avant)

    def test_option_sans_livre_ou_sans_dossier(self):
        with self.assertRaises(SystemExit):
            self.avec_args("--recompute")
        with self.assertRaises(SystemExit), mock.patch.object(
                sys, "argv", ["pmzilla_lab_library.py", "index", "--recompute", "pdf-livre"]):
            library.main(store=self.store)

    def test_aucun_fichier_dans_le_dossier_de_donnees(self):
        dossier = self.tmp / "data"
        dossier.mkdir(exist_ok=True)
        self.avec_args("--recompute", "pdf-livre")
        self.assertEqual(list(dossier.iterdir()), [])

    RAPPEL = ("Restore point: a labelled database backup taken before this run "
              "(DB_BACKUP_DATE=YYYY-MM-DD-<label> bash tools/db_backup.sh).")

    def test_le_rappel_du_point_de_retour_vient_en_premier(self):
        sortie = self.avec_args("--recompute", "pdf-livre")
        self.assertEqual(sortie.splitlines()[0], self.RAPPEL)
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            library.index([self.racine], ["epub-livre"], store=self.store)
        self.assertEqual(sortie.getvalue().splitlines()[0], self.RAPPEL)

    def test_pas_de_rappel_sans_recalcul_force(self):
        self.assertNotIn("Restore point", self.indexer())


class LegendePdfSansDoublon(Livres):
    def test_la_legende_n_apparait_qu_une_fois_dans_le_livre(self):
        tout = [r["text"] for r in self.chunks("pdf-livre.md")]
        self.assertEqual(sum("Un tableau kanban inventé" in t for t in tout), 1)
        self.assertEqual(sum("Courbe du délai de livraison inventée" in t for t in tout), 1)
        figure = self.chunks("pdf-livre.md", "figure")
        self.assertIn("Un tableau kanban inventé", figure[0]["text"])
        for r in self.chunks("pdf-livre.md", "text"):
            self.assertNotIn("Un tableau kanban inventé", r["text"])
            self.assertNotIn("Courbe du délai", r["text"])
        # le reste du paragraphe qui contenait la légende est conservé
        self.assertTrue(any("Un second paragraphe de la page trois." in r["text"]
                            for r in self.chunks("pdf-livre.md", "text")))

    def test_compteur_de_copies_retirees(self):
        stats: dict = {}
        library.split_passages(LIVRE_PDF.split("---\n", 2)[2], stats)
        self.assertEqual(stats, {"figures": 2, "copies_retirees": 2})
        self.assertIn("2 légendes du texte de page retirées", self.sortie)

    def methode(self, page: str, caption: str, source: str = "pdf") -> tuple[str, bool]:
        items = [["para", page], ["figure", {"id": "fig-0001", "source": source}, caption, ""]]
        retire = library._remove_caption_copy(items, 1, caption)
        return ("" if items[0][0] == "removed" else items[0][1]), retire

    def test_formes_de_la_copie_dans_le_texte_de_page(self):
        legende = "Figure 1.1 Un tableau kanban inventé"
        cas = {
            "ligne seule": (legende, "", True),
            "gras": ("**Figure 1.1** Un tableau kanban inventé", "", True),
            "italique": ("_Figure 1.1 Un tableau kanban inventé_", "", True),
            "casse et espaces": ("FIGURE  1.1   un tableau kanban inventé", "", True),
            "sur deux lignes": ("Figure 1.1 Un tableau\nkanban inventé", "", True),
            "entre deux lignes de texte": ("Avant.\n" + legende + "\nAprès.", "Avant.\nAprès.", True),
            "collée au paragraphe": ("Texte. " + legende, "Texte. " + legende, False),   # pas une ligne entière : laissée
            "absente": ("Un autre paragraphe sans rapport.", "Un autre paragraphe sans rapport.", False),
            "légende voisine différente": ("Figure 1.2 Autre figure", "Figure 1.2 Autre figure", False),
        }
        for nom, (page, attendu, retire) in cas.items():
            with self.subTest(nom):
                self.assertEqual(self.methode(page, legende), (attendu, retire))

    def test_seule_la_copie_la_plus_proche_est_retiree_et_la_recherche_s_arrete_a_la_figure_precedente(self):
        legende = "Figure 1.1 Un tableau kanban"
        items = [["para", legende], ["para", "texte"], ["figure", {"source": "pdf"}, "Autre légende", ""],
                 ["para", "texte de la page"], ["para", legende], ["figure", {"source": "pdf"}, legende, ""]]
        self.assertTrue(library._remove_caption_copy(items, 5, legende))
        self.assertEqual(items[0], ["para", legende])                  # la liste des figures du début n'est pas touchée
        self.assertEqual(items[4], ["removed"])
        items = [["para", legende], ["figure", {"source": "pdf"}, "Autre", ""], ["para", "texte"],
                 ["figure", {"source": "pdf"}, legende, ""]]
        self.assertFalse(library._remove_caption_copy(items, 3, legende))   # arrêt à la figure précédente
        self.assertEqual(items[0], ["para", legende])

    def test_les_epub_ne_sont_pas_dedoublonnes(self):
        """Un EPUB a déjà retiré la légende voisine à la conversion : le texte n'est pas retouché."""
        passages = library.split_passages(
            f"# T\n\n{TEXTE}\n\nFigure 1.1 Une légende\n\n"
            "<!-- figure id=fig-0001 source=epub -->\nLégende : Figure 1.1 Une légende\n")
        self.assertTrue(any("Figure 1.1 Une légende" in p.text for p in passages if p.kind == "texte"))

    @unittest.skipUnless(importlib.util.find_spec("pymupdf4llm"), "PyMuPDF absent")
    def test_integration_sur_un_vrai_pdf_converti(self):
        import pymupdf
        import convert_books as cb
        pdf = self.tmp / "reel.pdf"
        document = pymupdf.open()
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(60, 40, 540, 90), "La Figure 1.1 montre un diagramme inventé du flux.",
                            fontsize=10)
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 90), False)
        pixmap.set_rect(pixmap.irect, (200, 50, 50))
        page.insert_image(pymupdf.Rect(60, 100, 260, 200), pixmap=pixmap)
        page.insert_textbox(pymupdf.Rect(60, 205, 400, 235), "Figure 1.1 Un diagramme inventé du flux", fontsize=10)
        document.save(str(pdf))
        document.close()
        markdown, _ = cb.convert_pdf(pdf)
        self.assertIn("<!-- figure id=fig-0001 source=pdf page=1", markdown)
        passages = library.split_passages(markdown.split("---\n", 2)[2])
        legendes = [p for p in passages if "Un diagramme inventé du flux" in p.text]
        self.assertEqual([p.kind for p in legendes], ["figure"])               # une seule fois, dans le passage figure
        self.assertIn("La Figure 1.1 montre un diagramme inventé du flux.", legendes[0].text)   # phrase de renvoi

    def test_motif_de_libelle_identique_a_celui_de_la_conversion(self):
        import convert_books as cb
        self.assertEqual((library.LABEL.pattern, library.LABEL.flags), (cb.LABEL.pattern, cb.LABEL.flags))


class PhraseDeRenvoi(unittest.TestCase):
    def phrase(self, paragraphes: list[str], libelle: str, position: int | None = None) -> str:
        items = [["para", p] for p in paragraphes]
        items.insert(len(items) if position is None else position, ["figure", {}, f"{libelle} x", ""])
        return library._referring_sentence(items, items.index(next(i for i in items if i[0] == "figure")), libelle)

    def test_phrase_contenant_le_libelle(self):
        self.assertEqual(self.phrase(["Avant. Comme le montre la Figure 1.2, le délai augmente. Après."], "Figure 1.2"),
                         "Comme le montre la Figure 1.2, le délai augmente.")

    def test_libelle_voisin_non_confondu(self):
        self.assertEqual(self.phrase(["La Figure 1.21 est autre chose.", "La Figure 1.2 est la bonne."], "Figure 1.2"),
                         "La Figure 1.2 est la bonne.")
        self.assertEqual(self.phrase(["Voir la Figure 1.2."], "Figure 1.2"), "Voir la Figure 1.2.")
        self.assertEqual(self.phrase(["Rien ici."], "Figure 1.2"), "")

    def test_la_plus_proche_est_choisie_et_la_longueur_limitee(self):
        paragraphes = ["Loin : Figure 2.1 ici.", "x", "x", "x", "Près : Figure 2.1 là."]
        self.assertEqual(self.phrase(paragraphes, "Figure 2.1"), "Près : Figure 2.1 là.")
        long = "Figure 2.1 " + "mot " * 300
        self.assertLessEqual(len(self.phrase([long], "Figure 2.1")), library.REFERENCE_MAX)

    def test_espaces_et_casse_du_libelle(self):
        self.assertEqual(self.phrase(["Voir figure  1.2 ci-dessous."], "Figure 1.2"), "Voir figure 1.2 ci-dessous.")


class Types(Livres):
    """Le paramètre `types` de la recherche, lu par PostgresLibrary dans une base jetable (sautée sans base)."""

    def setUp(self):
        Base.setUp(self)             # pas Livres.setUp : l'indexation se fait ici dans la base jetable, pas dans le faux magasin
        sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
        import pg_demo
        self.base = pg_demo.ThrowawayDatabase(self)            # saute le test sans base
        brut = self.base._raw()
        brut.execute("TRUNCATE knowledge.chunks, knowledge.book_collections, knowledge.books, knowledge.collections")
        brut.commit()

        def connexion():
            conn = pg_demo.db.connect(self.base.url, password=pg_demo.base.MOT_DE_PASSE)
            self.base.opened.append(conn)
            return conn
        self.store = library.KnowledgeStore(connect=connexion)
        patch = mock.patch.object(library, "embed", fake_embed_1024)        # 1024 dimensions, comme la base
        patch.start()
        self.addCleanup(patch.stop)
        self.ecrire_livres()
        self.sortie = self.indexer()
        self.biblio = knowledge_library.PostgresLibrary(connect=self.base.connect, embed=fake_embed_1024)

    def test_texte_seul_par_defaut(self):
        hits = self.biblio.search("tableau kanban limite de travail", None, 10)
        self.assertTrue(hits)
        self.assertEqual({h["kind"] for h in hits}, {"texte"})
        self.assertTrue(all("ref" not in h for h in hits))

    def test_figures_seules(self):
        hits = self.biblio.search("tableau kanban", None, 10, types=["figure"])
        self.assertEqual({h["kind"] for h in hits}, {"figure"})
        premier = next(h for h in hits if h["file"] == "pdf-livre.md" and h["ref"]["label"] == "Figure 1.1")
        self.assertEqual(premier["ref"]["page"], 1)
        self.assertEqual(premier["ref"]["image"], "Bibliotheque-Images/pdf-livre/fig-0001.png")
        self.assertIsInstance(premier["ref"]["image"], str)                 # un simple texte
        self.assertEqual(premier["book"], "Livre PDF inventé")
        self.assertEqual(premier["section"], "Partie un > Le flux")
        self.assertEqual(len(hits), 4)                                       # les quatre figures de la bibliothèque

    def test_les_deux(self):
        hits = self.biblio.search("tableau kanban", None, 20, types=["texte", "figure"])
        self.assertEqual({h["kind"] for h in hits}, {"texte", "figure"})
        self.assertEqual(len(self.biblio.search("tableau kanban", None, 20, types="figure")), 4)   # une chaîne est acceptée

    def test_filtres_combines(self):
        hits = self.biblio.search("équipes", ["organisation"], 10, types=["figure"])
        self.assertEqual({h["file"] for h in hits}, {"epub-livre.md"})
        hits = self.biblio.search("équipes", ["flow"], 10, types=["figure"])
        self.assertEqual({h["file"] for h in hits}, {"pdf-livre.md"})

    def test_types_invalides(self):
        for invalide in (["image"], ["texte", "photo"], []):
            with self.subTest(invalide):
                with self.assertRaises(ValueError):
                    self.biblio.search("kanban", None, 5, types=invalide)

    def test_une_recherche_de_figures_n_est_pas_noyee_par_les_passages_de_texte(self):
        """Les 200 meilleurs résultats du plein texte seraient tous du texte : le filtre est dans la requête."""
        sections = "".join(f"## Section {n}\n\n{TEXTE}kanban kanban kanban numéro {n}.\n\n" for n in range(260))
        self.ecrire("flow/long.md", "# Long\n\n" + sections)
        self.indexer()
        hits = self.biblio.search("kanban", None, 10, types=["figure"])
        self.assertEqual({h["kind"] for h in hits}, {"figure"})
        self.assertGreaterEqual(len(hits), 1)

    def test_lecture_kind_et_ref(self):
        figure = next(h for h in self.biblio.search("tableau kanban", None, 10, types=["figure"])
                      if h["file"] == "pdf-livre.md")
        lu = self.biblio.read(figure["passage_id"], 1, 1)
        passage = next(p for p in lu["passages"] if p["passage_id"] == figure["passage_id"])
        self.assertEqual(passage["kind"], "figure")
        self.assertEqual(passage["ref"]["id"], "fig-0001")
        voisins = [p for p in lu["passages"] if p["passage_id"] != figure["passage_id"]]
        self.assertTrue(voisins)
        for voisin in voisins:
            self.assertEqual(voisin["kind"], "texte")
            self.assertNotIn("ref", voisin)

    def test_liste_des_livres_compte_les_figures(self):
        par_fichier = {b["file"]: b["figures"] for b in self.biblio.books(None)}
        self.assertEqual(par_fichier, {"pdf-livre.md": 2, "epub-livre.md": 2, "texte.md": 0})

    def test_aucun_acces_aux_images_en_indexant_cherchant_et_lisant(self):
        """Le chemin d'une image n'est qu'un texte : aucune ouverture, lecture ou test d'existence d'un fichier sous
        Bibliotheque-Images pendant l'indexation, la recherche et la lecture."""
        acces: list[str] = []

        def surveille(original):
            def enveloppe(chemin, *arguments, **options):
                if "Bibliotheque-Images" in str(chemin):
                    acces.append(str(chemin))
                return original(chemin, *arguments, **options)
            return enveloppe

        def surveille_methode(original):
            def enveloppe(self, *arguments, **options):
                if "Bibliotheque-Images" in str(self):
                    acces.append(str(self))
                return original(self, *arguments, **options)
            return enveloppe

        with contextlib.ExitStack() as pile:
            pile.enter_context(mock.patch.object(builtins, "open", surveille(builtins.open)))
            pile.enter_context(mock.patch.object(io, "open", surveille(io.open)))
            pile.enter_context(mock.patch.object(os.path, "exists", surveille(os.path.exists)))
            pile.enter_context(mock.patch.object(os.path, "isfile", surveille(os.path.isfile)))
            for nom in ("read_bytes", "exists", "is_file", "open", "stat"):
                pile.enter_context(mock.patch.object(Path, nom, surveille_methode(getattr(Path, nom))))
            self.ecrire("flow/autre.md", LIVRE_PDF.replace("Livre PDF inventé", "Autre livre"))
            self.indexer()
            for hit in self.biblio.search("tableau kanban", None, 10, types=["texte", "figure"]):
                self.biblio.read(hit["passage_id"], 2, 2)
        self.assertEqual(acces, [])


class ServeurSansImages(unittest.TestCase):
    def test_serveur_ne_declare_que_quatre_outils_sans_acces_aux_images(self):
        source = (Path(library.__file__)).read_text(encoding="utf-8")
        outils = [n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)
                  and any("tool" in ast.unparse(d) for d in n.decorator_list)]
        self.assertEqual(sorted(outils), ["list_books", "list_collections", "list_due_reviews", "read_passage", "search_cases",
                                          "search_experiments", "search_library"])
        for nom in outils:
            for verbe in ("start", "note", "postpone", "drop", "close"):
                self.assertNotIn(verbe, nom)
        for interdit in ("get_figure", "base64", "read_bytes", "webbrowser", "subprocess", "Pixmap", "get_pixmap"):
            self.assertNotIn(interdit, source)
        signature = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)
                         and n.name == "search_library")
        self.assertIn("types", [a.arg for a in signature.args.args])


class Regles(unittest.TestCase):
    def test_regle_de_citation_d_une_figure_dans_claude_md(self):
        regle = (Path(__file__).resolve().parents[2] / "CLAUDE.md").read_text(encoding="utf-8")
        for attendu in ("**Figures.**", 'types ["figure"]', "Figure X.Y", "page", "section", "inference formula",
                        "you cannot open", "caption", "redrawn"):
            self.assertIn(attendu, regle, attendu)


if __name__ == "__main__":
    unittest.main()
