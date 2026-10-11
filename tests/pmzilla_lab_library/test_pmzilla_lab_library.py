"""
Tests de la bibliothèque (tools/pmzilla_lab_library.py) sur des livres et des articles inventés.

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/pmzilla_lab_library -v

Tout se passe dans un dossier temporaire : l'index, le catalogue et les livres sont inventés, jamais
Bibliotheque-MD ni l'index réel. Aucun accès réseau : `embed` (Ollama) est remplacé par un plongement
déterministe fondé sur les mots, les appels sont comptés pour prouver qu'une indexation incrémentale
ne recalcule rien d'inutile.
"""
import ast
import contextlib
import hashlib
import io
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import identifiants_personnels  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]

DIM = 128


def fake_embed(texts):
    """Sac de mots haché, normalisé : deux textes qui partagent des mots sont proches."""
    out = np.zeros((len(texts), DIM), dtype=np.float32)
    for row, text in enumerate(texts):
        for word in re.findall(r"\w+", text.lower()):
            out[row, int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.where(norms == 0, 1, norms)


def livre(titre: str, sections: dict[str, str], entete: str = "") -> str:
    texte = f'---\ntitle: "{titre}"\n{entete}---\n\n'
    for section, corps in sections.items():
        texte += f"## {section}\n\n{corps}\n\n"
    return texte


FLUX = {
    "Limiter le travail en cours": "La limite de travail en cours (WIP) réduit le cycle time et stabilise le flux "
                                   "dans un tableau kanban ; une équipe qui commence moins finit plus vite.",
    "Prévoir avec le débit": "Le débit mesuré sur les semaines passées permet une prévision probabiliste "
                             "sans estimation : on simule le nombre d'éléments terminés par semaine.",
}
DISCOVERY = {
    "Entretiens": "Les entretiens réguliers avec les utilisateurs alimentent un arbre d'opportunités ; "
                  "chaque hypothèse de discovery se teste par une expérimentation légère.",
}
TOPOLOGIES = {
    "Charge cognitive": "Une équipe alignée sur un flux porte une charge cognitive limitée ; les interactions "
                        "entre équipes se choisissent : collaboration, facilitation ou service.",
}
ARTICLE = {
    "Corps": "Les métriques de flux agrégées cachent les différences entre équipes ; un article récent "
             "qui discute le cycle time et le débit dans une grande organisation produit.",
}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.racine = self.tmp / "collections"
        self.catalogue = self.tmp / "catalogue.yaml"
        self.calls = 0

        def compte(texts):
            self.calls += 1
            return fake_embed(texts)

        for patch in (
            mock.patch.object(library, "DATA_DIR", self.tmp / "data"),
            mock.patch.object(library, "DB_PATH", self.tmp / "data" / "library.sqlite"),
            mock.patch.object(library, "CATALOGUE_PATH", self.catalogue),
            mock.patch.object(library, "embed", compte),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.ecrire("flow/Flux.md", livre("Flux inventé", FLUX))
        self.ecrire("produit/Discovery.md", livre("Discovery inventée", DISCOVERY))
        self.ecrire("organisation/Topologies.md", livre("Topologies inventées", TOPOLOGIES))
        self.ecrire("watch/article-flux.md", livre(
            "Article de la watch", ARTICLE,
            'url: https://exemple.test/a\nsource: exemple.test\npublished: "2026-09-30"\n'))

    def ecrire(self, relatif: str, texte: str) -> Path:
        chemin = self.racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def indexer(self) -> str:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            library.index([self.racine])
        return sortie.getvalue()

    def livres(self) -> dict:
        db = library.connect()
        return {r[0]: r[1:] for r in db.execute("SELECT file_name, title, collections, sha256 FROM books")}


class Indexation(Base):
    def test_premiere_indexation(self):
        sortie = self.indexer()
        self.assertIn("Indexed: 4", sortie)
        self.assertEqual(set(self.livres()), {"Flux.md", "Discovery.md", "Topologies.md", "article-flux.md"})
        self.assertEqual(self.livres()["Flux.md"][0], "Flux inventé")

    def test_inchange_ne_recalcule_rien(self):
        self.indexer()
        appels = self.calls
        sortie = self.indexer()
        self.assertIn("Indexed: 0 · unchanged: 4", sortie)
        self.assertEqual(self.calls, appels)

    def test_ajout(self):
        self.indexer()
        appels = self.calls
        self.ecrire("flow/Nouveau.md", livre("Nouveau livre", {"Section": "Un texte assez long pour faire un "
                                                              "passage : métriques, files d'attente et loi de Little."}))
        sortie = self.indexer()
        self.assertIn("Indexed: 1 · unchanged: 4", sortie)
        self.assertGreater(self.calls, appels)
        self.assertIn("Nouveau.md", self.livres())

    def test_modification_remplace_les_passages(self):
        self.indexer()
        self.ecrire("flow/Flux.md", livre("Flux inventé", {
            "Seule section": "Texte entièrement nouveau sur la loi de Little et les files d'attente, "
                             "assez long pour dépasser le seuil de quatre-vingts caractères."}))
        sortie = self.indexer()
        self.assertIn("Indexed: 1 · unchanged: 3", sortie)
        db = library.connect()
        sections = [r[0] for r in db.execute(
            "SELECT c.section FROM chunks c JOIN books b ON b.id = c.book_id WHERE b.file_name = 'Flux.md'")]
        self.assertEqual(sections, ["Seule section"])
        # l'index plein texte suit : l'ancien vocabulaire a disparu
        self.assertEqual(db.execute("SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH 'kanban'").fetchone()[0], 0)

    def test_fichier_supprime_sort_de_l_index(self):
        self.indexer()
        (self.racine / "produit" / "Discovery.md").unlink()
        sortie = self.indexer()
        self.assertIn("removed: Discovery.md", sortie)
        self.assertNotIn("Discovery.md", self.livres())
        self.assertEqual(library.connect().execute(
            "SELECT COUNT(*) FROM chunks WHERE text LIKE '%arbre d''opportunités%'").fetchone()[0], 0)

    def test_changement_de_collection_sans_recalcul(self):
        self.indexer()
        appels = self.calls
        shutil.move(self.racine / "produit" / "Discovery.md", self.racine / "organisation" / "Discovery.md")
        self.indexer()
        self.assertEqual(self.calls, appels)
        self.assertEqual(self.livres()["Discovery.md"][1], "organisation")

    def test_livre_dans_deux_collections_indexe_une_fois(self):
        shutil.copy(self.racine / "flow" / "Flux.md", self.racine / "organisation" / "Flux.md")
        sortie = self.indexer()
        self.assertIn("Indexed: 4", sortie)
        self.assertEqual(self.livres()["Flux.md"][1], "flow|organisation")

    def test_catalogue_change_titre_et_auteur_sans_recalcul(self):
        self.indexer()
        appels = self.calls
        self.catalogue.write_text(
            "Flux.md:\n  titre: Titre du catalogue\n  auteurs: [Auteur Un, Auteur Deux]\n"
            "Discovery.md:\n  titre: Sans auteur\n", encoding="utf-8")
        self.indexer()
        self.assertEqual(self.calls, appels)
        self.assertEqual(self.livres()["Flux.md"][0], "Titre du catalogue")
        hit = library.Library().search("kanban", None, 1)[0]
        self.assertEqual(hit["book"], "Titre du catalogue")
        self.assertEqual(hit["author"], "Auteur Un, Auteur Deux")
        hit = library.Library().search("arbre d'opportunités", ["produit"], 1)[0]
        self.assertEqual(hit["author"], "auteur non indiqué")

    def test_changement_de_modele_reindexe(self):
        self.indexer()
        with mock.patch.object(library, "EMBED_MODEL", "autre-modele"):
            self.assertIn("Indexed: 4", self.indexer())

    def test_fichiers_underscore_ignores_et_dossier_absent(self):
        self.ecrire("flow/_note.md", "# brouillon\n\nignoré")
        self.assertIn("Indexed: 4", self.indexer())
        with self.assertRaises(SystemExit):
            library.index([self.tmp / "absent"])


class Decoupage(unittest.TestCase):
    def test_sections_hierarchiques_et_debris(self):
        corps = ("# Partie\n\n## Chapitre\n\n" + "Un paragraphe suffisamment long pour être gardé. " * 3 +
                 "\n\n## Autre\n\n12\n\n### Sous-section\n\n" + "Autre texte assez long pour passer le seuil. " * 3)
        passages = library.split_passages(corps)
        self.assertEqual([p.section for p in passages], ["Partie > Chapitre", "Partie > Autre > Sous-section"])

    def test_gros_paragraphe_coupe(self):
        passages = library.split_passages("# T\n\n" + "mot " * 2000)
        self.assertGreater(len(passages), 1)
        self.assertTrue(all(len(p.text) <= library.CHUNK_TARGET * 2 for p in passages))

    def test_sans_titre(self):
        passages = library.split_passages("Texte sans aucun titre mais assez long pour dépasser le seuil de "
                                          "quatre-vingts caractères exigé.")
        self.assertEqual(passages[0].section, "(no heading)")

    def test_meta_et_titre(self):
        texte = '---\ntitle: "Mon titre"\nsource: site.test\nurl: https://site.test/x\n---\n\ncorps'
        self.assertEqual(library.read_title(texte, "repli")[0], "Mon titre")
        self.assertEqual(library.read_title("corps seul", "repli"), ("repli", "corps seul"))
        meta = library.read_meta(texte)
        self.assertEqual(meta["author"], "site.test (auteur non indiqué)")  # jamais un nom inventé


class Recherche(Base):
    def setUp(self):
        super().setUp()
        self.indexer()
        self.biblio = library.Library()

    def test_pertinence_de_base(self):
        premier = self.biblio.search("charge cognitive des équipes", None, 3)[0]
        self.assertEqual(premier["file"], "Topologies.md")
        premier = self.biblio.search("limite de travail en cours kanban", None, 3)[0]
        self.assertEqual(premier["file"], "Flux.md")

    def test_section_et_champs_renvoyes(self):
        hit = self.biblio.search("prévision probabiliste débit", None, 1)[0]
        self.assertEqual(hit["section"], "Prévoir avec le débit")
        self.assertEqual(hit["book"], "Flux inventé")
        self.assertEqual(hit["collections"], ["flow"])
        self.assertIn("passage_id", hit)

    def test_article_porte_url_date_et_site(self):
        hit = self.biblio.search("métriques de flux agrégées", ["watch"], 1)[0]
        self.assertEqual(hit["url"], "https://exemple.test/a")
        self.assertEqual(hit["published"], "2026-09-30")
        self.assertEqual(hit["author"], "exemple.test (auteur non indiqué)")

    def test_filtre_par_collection(self):
        hits = self.biblio.search("flux cycle time débit", ["produit"], 10)
        self.assertEqual({h["file"] for h in hits}, {"Discovery.md"})
        self.assertEqual(self.biblio.search("flux", ["inconnue"], 10), [])

    def test_filtre_de_date_garde_les_livres(self):
        hits = self.biblio.search("flux cycle time débit", None, 10, since="2026-10-15")
        self.assertNotIn("article-flux.md", {h["file"] for h in hits})
        self.assertIn("Flux.md", {h["file"] for h in hits})
        hits = self.biblio.search("flux cycle time débit", None, 10, since="2026-09-01")
        self.assertIn("article-flux.md", {h["file"] for h in hits})

    def test_limite(self):
        self.assertEqual(len(self.biblio.search("flux équipes", None, 2)), 2)

    def test_lecture_avec_voisins(self):
        hit = self.biblio.search("prévision probabiliste débit", None, 1)[0]
        lu = self.biblio.read(hit["passage_id"], 1, 0)
        self.assertEqual(lu["book"], "Flux inventé")
        self.assertEqual([p["section"] for p in lu["passages"]], ["Limiter le travail en cours", "Prévoir avec le débit"])
        self.assertIn("error", self.biblio.read(999999, 0, 0))

    def test_collections_et_livres(self):
        self.assertEqual(self.biblio.collections(), {"flow": 1, "organisation": 1, "produit": 1, "watch": 1})
        self.assertEqual([b["file"] for b in self.biblio.books("produit")], ["Discovery.md"])
        self.assertEqual(len(self.biblio.books(None)), 4)

    def test_requete_sans_mot(self):
        self.assertIsInstance(self.biblio.search("???", None, 3), list)


class Renommage(Base):
    """Collection « veille » devenue « watch » : plus d'alias, sous-commande rename-collection."""

    def setUp(self):
        super().setUp()
        self.indexer()
        self.appels = self.calls

    def stocke(self, nom: str):
        """Remet l'index dans l'état d'avant le renommage : le livre est stocké sous `nom`."""
        db = library.connect()
        db.execute("UPDATE books SET collections = ? WHERE file_name = 'article-flux.md'", (nom,))
        db.commit()

    def renommer(self, *args) -> str:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            library.rename_collection(*args)
        return sortie.getvalue()

    def collections_stockees(self):
        return library.connect().execute(
            "SELECT collections FROM books WHERE file_name = 'article-flux.md'").fetchone()[0]

    def test_ancien_index_montre_le_nom_stocke_et_le_nom_actuel_ne_trouve_rien(self):
        self.stocke("veille")
        biblio = library.Library()
        self.assertEqual(biblio.collections().get("veille"), 1)
        self.assertNotIn("watch", biblio.collections())
        self.assertEqual(biblio.search("métriques de flux agrégées", ["watch"], 5), [])
        self.assertFalse(hasattr(biblio, "stored_aliases"))
        self.assertFalse(hasattr(library, "COLLECTION_ALIASES"))

    def test_nouvel_index_ne_trouve_rien_par_l_ancien_nom(self):
        biblio = library.Library()
        self.assertEqual(biblio.search("métriques de flux agrégées", ["veille"], 5), [])
        hits = biblio.search("métriques de flux agrégées", ["watch"], 5)
        self.assertEqual({h["file"] for h in hits}, {"article-flux.md"})

    def test_les_deux_noms_stockes_restent_distincts(self):
        db = library.connect()
        db.execute("UPDATE books SET collections = 'veille' WHERE file_name = 'article-flux.md'")
        db.execute("UPDATE books SET collections = 'watch' WHERE file_name = 'Flux.md'")
        db.commit()
        biblio = library.Library()
        self.assertEqual(biblio.collections()["watch"], 1)
        self.assertEqual(biblio.collections()["veille"], 1)
        hits = biblio.search("flux cycle time débit", ["watch"], 10)
        self.assertEqual({h["file"] for h in hits}, {"Flux.md"})

    def test_dossier_ancien_nom_indexe_sous_son_propre_nom_sans_avertissement(self):
        shutil.move(self.racine / "watch", self.racine / "veille")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.indexer()
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(self.collections_stockees(), "veille")

    def test_deplacement_de_dossier_ne_recalcule_rien(self):
        self.stocke("veille")
        shutil.move(self.racine / "watch", self.racine / "veille")
        shutil.move(self.racine / "veille", self.racine / "watch")
        sortie = self.indexer()
        self.assertIn("Indexed: 0 · unchanged: 4", sortie)
        self.assertEqual(self.calls, self.appels)
        self.assertEqual(self.collections_stockees(), "watch")

    def test_rename_collection_en_place_sans_recalcul(self):
        self.stocke("veille")
        db = library.connect()
        avant = db.execute("SELECT id, book_id, position, embedding, text FROM chunks ORDER BY id").fetchall()
        autres = db.execute("SELECT file_name, sha256, collections, title, meta FROM books "
                            "WHERE file_name != 'article-flux.md' ORDER BY id").fetchall()
        sortie = self.renommer("veille", "watch")
        self.assertIn("1 books", sortie)
        self.assertEqual(self.collections_stockees(), "watch")
        db = library.connect()
        self.assertEqual(db.execute("SELECT id, book_id, position, embedding, text FROM chunks ORDER BY id").fetchall(), avant)
        self.assertEqual(db.execute("SELECT file_name, sha256, collections, title, meta FROM books "
                                    "WHERE file_name != 'article-flux.md' ORDER BY id").fetchall(), autres)
        self.assertEqual(self.calls, self.appels)
        self.assertTrue(db.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'agrégées'").fetchall())

    def test_rename_collection_dry_run_et_idempotence(self):
        self.stocke("veille")
        sortie = self.renommer("veille", "watch", True)
        self.assertIn("would be renamed", sortie)
        self.assertEqual(self.collections_stockees(), "veille")
        self.renommer("veille", "watch")
        self.assertIn("nothing to do", self.renommer("veille", "watch"))
        self.assertEqual(self.collections_stockees(), "watch")

    def test_rename_collection_dedoublonne(self):
        self.stocke("veille|watch")
        self.assertIn("already in 'watch'", self.renommer("veille", "watch"))
        self.assertEqual(self.collections_stockees(), "watch")

    def test_rename_collection_en_ligne_de_commande(self):
        self.stocke("veille")
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["x", "rename-collection", "veille", "watch", "--dry-run"]), \
                contextlib.redirect_stdout(sortie):
            library.main()
        self.assertIn("would be renamed", sortie.getvalue())
        self.assertEqual(self.collections_stockees(), "veille")


class DescriptionDeSearchLibrary(unittest.TestCase):
    def test_description_sans_identifiant_personnel(self):
        arbre = ast.parse((RACINE / "tools" / "pmzilla_lab_library.py").read_text(encoding="utf-8"))
        docstring = next(n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == "search_library")
        docstring = ast.get_docstring(docstring) or ""
        self.assertIn('"' + library.OWN_COLLECTION + '"', docstring)
        self.assertIn("the user's", docstring)
        for identifiant in identifiants_personnels.identifiants(RACINE):
            self.assertFalse(identifiant in docstring.lower(), "la description de search_library contient un identifiant personnel")


if __name__ == "__main__":
    unittest.main()
