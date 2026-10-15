"""
Tests de la bibliothèque (tools/pmzilla_lab_library.py) sur des livres et des articles inventés.

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/pmzilla_lab_library -v

Tout se passe dans un dossier temporaire : le catalogue et les livres sont inventés, jamais Bibliotheque-MD
ni la vraie base. L'indexeur écrit dans un faux magasin en mémoire (fake_store.FakeStore, même interface que
KnowledgeStore) ; la classe AvecBase refait l'essentiel sur une base jetable (sautée sans base, lancée par
tools/dbtest.sh), et les tests de recherche et de lecture (Recherche, RenommageLu) indexent dans cette base puis lisent par
PostgresLibrary. Aucun accès réseau : `embed` (Ollama) est remplacé par un plongement déterministe fondé sur
les mots, les appels sont comptés pour prouver qu'une indexation incrémentale ne recalcule rien d'inutile.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import identifiants_personnels  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402
from fake_store import FakeStore  # noqa: E402
import knowledge_library  # noqa: E402

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


def fake_embed_1024(texts):
    """Le même plongement, complété de zéros jusqu'aux 1024 dimensions de la base."""
    out = np.zeros((len(texts), 1024), dtype=np.float32)
    out[:, :DIM] = fake_embed(texts)
    return out


def code_de_sortie(arret: SystemExit) -> int:
    """Code de sortie du processus pour un SystemExit : un message vaut 1."""
    code = arret.code
    return 0 if code is None else (1 if isinstance(code, str) else int(code))


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
        self.plongement = fake_embed
        self.store = FakeStore()

        def compte(texts):
            self.calls += 1
            return self.plongement(texts)

        for patch in (
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

    def indexer(self, **options) -> str:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            library.index([self.racine], store=self.store, **options)
        return sortie.getvalue()

    def livres(self) -> dict:
        return {nom: (b.title, "|".join(sorted(b.collections)), b.sha256) for nom, b in self.store.stored_books().items()}

    def textes(self, fichier: str | None = None) -> list[str]:
        return [p["text"] for nom, b in sorted(self.store.books.items()) if fichier in (None, nom) for p in b["passages"]]

    def fichiers_sqlite(self) -> list[Path]:
        return sorted(self.tmp.rglob("*.sqlite*"))


class LectureEnBase(Base):
    """Indexe dans une base jetable migrée (KnowledgeStore, tests/library_backend/pg_demo.py), tables knowledge vidées avant chaque test, puis lit
    par PostgresLibrary. Sautée sans base ; lancée par l'utilisateur avec bash tools/dbtest.sh. Jamais la vraie base."""

    def setUp(self):
        super().setUp()
        sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
        import pg_demo
        self.pg = pg_demo
        self.base = pg_demo.ThrowawayDatabase(self)            # saute le test sans base
        self.lecture = self.base._raw()
        self.lecture.execute("TRUNCATE knowledge.chunks, knowledge.book_collections, knowledge.books, knowledge.collections")
        self.lecture.commit()
        self.lecture.autocommit = True
        self.plongement = fake_embed_1024
        self.store = self.magasin()

    def connexion(self):
        conn = self.pg.db.connect(self.base.url, password=self.pg.base.MOT_DE_PASSE)
        self.base.opened.append(conn)
        return conn

    def magasin(self):
        return library.KnowledgeStore(connect=self.connexion)

    def valeur(self, sql, params=None):
        return self.lecture.execute(sql, params).fetchone()[0]

    def bibliotheque(self) -> "knowledge_library.PostgresLibrary":
        """La voie de lecture du serveur sur le contenu de la base jetable."""
        return knowledge_library.PostgresLibrary(connect=self.base.connect, embed=fake_embed_1024)


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
        sections = [p["section"] for p in self.store.books["Flux.md"]["passages"]]
        self.assertEqual(sections, ["Seule section"])
        self.assertFalse([t for t in self.textes() if "kanban" in t])      # l'ancien vocabulaire a disparu

    def test_fichier_supprime_sort_de_l_index(self):
        self.indexer()
        (self.racine / "produit" / "Discovery.md").unlink()
        sortie = self.indexer()
        self.assertIn("removed: Discovery.md", sortie)
        self.assertNotIn("Discovery.md", self.livres())
        self.assertFalse([t for t in self.textes() if "arbre d'opportunités" in t])

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
        self.assertEqual(self.store.books["Flux.md"]["meta"]["author"], "Auteur Un, Auteur Deux")
        self.assertEqual(self.store.books["Discovery.md"]["meta"]["author"], "auteur non indiqué")

    def test_changement_de_modele_reindexe(self):
        self.indexer()
        with mock.patch.object(library, "EMBED_MODEL", "autre-modele"):
            self.assertIn("Indexed: 4", self.indexer())

    def test_fichiers_underscore_ignores_et_dossier_absent(self):
        self.ecrire("flow/_note.md", "# brouillon\n\nignoré")
        self.assertIn("Indexed: 4", self.indexer())
        with self.assertRaises(SystemExit) as arret:
            library.index([self.tmp / "absent"], store=self.store)
        self.assertIn("Not a folder", str(arret.exception))

    def test_livre_deja_copie_par_l_ancien_import_est_inchange(self):
        """Hash, modèle, titre, métadonnées (autre ordre des clés) et collections identiques : aucun recalcul (design.md D1)."""
        self.indexer()
        ancien = FakeStore()
        for nom, b in self.store.books.items():
            meta = dict(reversed(list(b["meta"].items())))
            ancien.books[nom] = dict(b, meta=meta, collections=set(b["collections"]), passages=list(b["passages"]))
            ancien.collections |= b["collections"]
        self.store, appels = ancien, self.calls
        self.assertIn("Indexed: 0 · unchanged: 4", self.indexer())
        self.assertEqual(self.calls, appels)
        self.assertEqual(ancien.writes, [])                                   # rien n'est réécrit

    def test_passages_dans_l_ordre_avec_le_genre_text(self):
        self.indexer()
        for nom, b in self.store.books.items():
            self.assertEqual([p["position"] for p in b["passages"]], list(range(len(b["passages"]))), nom)
            self.assertEqual({p["kind"] for p in b["passages"]}, {"text"}, nom)
            self.assertTrue(all(p["ref"] == {} for p in b["passages"]))

    def test_vecteur_arrondi_en_demi_precision(self):
        self.indexer()
        b = self.store.books["Flux.md"]
        for p in b["passages"]:
            attendu = fake_embed([f"{b['title']}\n{p['section']}\n{p['text']}"])[0].astype(np.float16)
            self.assertEqual(p["vector"].dtype, np.float16)
            self.assertEqual(p["vector"].tobytes(), attendu.tobytes())

    def test_taille_de_vecteur_fausse_arrete_le_livre_sans_texte(self):
        self.store = FakeStore(dimensions=1024)
        sortie, erreurs = io.StringIO(), io.StringIO()
        with self.assertRaises(SystemExit) as arret, contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreurs):
            library.index([self.racine], store=self.store)
        self.assertEqual(code_de_sortie(arret.exception), 1)
        tout = sortie.getvalue() + erreurs.getvalue() + str(arret.exception.code)
        self.assertIn("128 dimensions", tout)
        self.assertIn("1024", tout)
        self.assertNotIn("kanban", tout)                            # aucun texte de livre
        self.assertEqual(self.store.books, {})

    def test_livre_en_echec_absent_les_autres_ecrits_code_1(self):
        self.store.fail_on.add("Discovery.md")
        sortie, erreurs = io.StringIO(), io.StringIO()
        with self.assertRaises(SystemExit) as arret, contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreurs):
            library.index([self.racine], store=self.store)
        self.assertEqual(code_de_sortie(arret.exception), 1)
        self.assertIn("Discovery.md", str(arret.exception.code))
        self.assertEqual(set(self.store.books), {"Flux.md", "Topologies.md", "article-flux.md"})

    def test_collection_orpheline_supprimee_sans_recalcul(self):
        self.indexer()
        appels = self.calls
        shutil.move(self.racine / "produit" / "Discovery.md", self.racine / "organisation" / "Discovery.md")
        self.indexer()
        self.assertEqual(self.calls, appels)
        self.assertNotIn("produit", self.store.collections)
        self.assertIn("organisation", self.store.collections)

    def test_resume_nomme_la_base(self):
        sortie = self.indexer()
        self.assertRegex(sortie, r"Indexed: 4 · unchanged: 0 · passages in the index: \d+")
        self.assertIn("Index: database, schema knowledge", sortie)

    def test_aucun_fichier_sqlite_apres_index(self):
        self.indexer()
        self.indexer()
        self.assertEqual(self.fichiers_sqlite(), [])


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


class Recherche(LectureEnBase):
    """La recherche et la lecture du serveur sur des livres inventés indexés dans une base jetable (sautée sans base)."""

    def setUp(self):
        super().setUp()
        self.indexer()
        self.biblio = self.bibliotheque()

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

    def test_catalogue_titre_et_auteur_lus_par_la_recherche(self):
        self.catalogue.write_text(
            "Flux.md:\n  titre: Titre du catalogue\n  auteurs: [Auteur Un, Auteur Deux]\nDiscovery.md:\n  titre: Sans auteur\n", encoding="utf-8")
        self.indexer()
        biblio = self.bibliotheque()
        hit = biblio.search("kanban", None, 1)[0]
        self.assertEqual(hit["book"], "Titre du catalogue")
        self.assertEqual(hit["author"], "Auteur Un, Auteur Deux")
        self.assertEqual(biblio.search("arbre d'opportunités", ["produit"], 1)[0]["author"], "auteur non indiqué")

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
        self.store.books["article-flux.md"]["collections"] = set(nom.split("|"))
        self.store.collections |= set(nom.split("|"))

    def renommer(self, *args) -> str:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            library.rename_collection(*args, store=self.store)
        return sortie.getvalue()

    def collections_stockees(self):
        return "|".join(sorted(self.store.books["article-flux.md"]["collections"]))

    def passages(self) -> list:
        return [(nom, p["position"], p["section"], p["text"], p["kind"], p["vector"].tobytes())
                for nom, b in sorted(self.store.books.items()) for p in b["passages"]]

    def autres_livres(self) -> list:
        return [(nom, b["sha256"], sorted(b["collections"]), b["title"], b["meta"], b["indexed_at"])
                for nom, b in sorted(self.store.books.items()) if nom != "article-flux.md"]

    def test_dossier_ancien_nom_indexe_sous_le_nouveau_avec_avertissement(self):
        shutil.move(self.racine / "watch", self.racine / "veille")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            sortie = self.indexer()
        self.assertIn("'veille'", err.getvalue())
        self.assertIn("'watch'", err.getvalue())
        self.assertEqual(self.store.books["article-flux.md"]["collections"], {"watch"})
        self.assertIn("Indexed: 0 · unchanged: 4", sortie)
        self.assertEqual(self.calls, self.appels)

    def test_deplacement_de_dossier_ne_recalcule_rien(self):
        self.stocke("veille")
        shutil.move(self.racine / "watch", self.racine / "veille")
        shutil.move(self.racine / "veille", self.racine / "watch")
        sortie = self.indexer()
        self.assertIn("Indexed: 0 · unchanged: 4", sortie)
        self.assertEqual(self.calls, self.appels)
        self.assertEqual(self.store.books["article-flux.md"]["collections"], {"watch"})

    def test_rename_collection_en_place_sans_recalcul(self):
        self.stocke("veille")
        self.store.collections.discard("watch")
        avant, autres = self.passages(), self.autres_livres()
        sortie = self.renommer("veille", "watch")
        self.assertIn("1 books", sortie)
        self.assertIn("Vectors recomputed: 0", sortie)
        self.assertTrue(sortie.rstrip().endswith("Index: database, schema knowledge"), sortie)
        self.assertEqual(self.collections_stockees(), "watch")
        self.assertEqual(self.passages(), avant)
        self.assertEqual(self.autres_livres(), autres)
        self.assertEqual(self.calls, self.appels)
        self.assertNotIn("veille", self.store.collections)              # l'ancienne collection, inutilisée, disparaît
        self.assertIn("watch", self.store.collections)
        self.assertEqual(sum(w[0] == "collections" for w in self.store.writes), 1)   # une seule transaction

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
            library.main(store=self.store)
        self.assertIn("would be renamed", sortie.getvalue())
        self.assertEqual(self.collections_stockees(), "veille")
        self.assertEqual([w for w in self.store.writes if w[0] == "collections"], [])

    def test_rename_collection_base_injoignable_code_2(self):
        self.store = FakeStore(available=False)
        erreurs = io.StringIO()
        with self.assertRaises(SystemExit) as arret, contextlib.redirect_stderr(erreurs), \
                contextlib.redirect_stdout(io.StringIO()):
            self.renommer("veille", "watch")
        self.assertEqual(code_de_sortie(arret.exception), 2)
        self.assertIn("Database unreachable: nothing was renamed. Start it: bash tools/db_up.sh", erreurs.getvalue())

    def test_rename_collection_verrou_tenu_code_1(self):
        self.stocke("veille")
        self.store.locked = True
        with self.assertRaises(SystemExit) as arret, contextlib.redirect_stdout(io.StringIO()):
            self.renommer("veille", "watch")
        self.assertEqual(code_de_sortie(arret.exception), 1)
        self.assertIn("Another indexing run is in progress", str(arret.exception.code))
        self.assertEqual(self.collections_stockees(), "veille")

    def test_rename_collection_noms_invalides(self):
        for noms in (("", "watch"), ("veille", "")):
            with self.assertRaises(SystemExit):
                self.renommer(*noms)
        self.assertEqual(self.store.opened, 1)                          # seule l'indexation du setUp a ouvert le magasin

    def test_aucun_fichier_sqlite_apres_index_et_renommage(self):
        self.stocke("veille")
        self.renommer("veille", "watch")
        self.indexer()
        self.assertEqual(self.fichiers_sqlite(), [])


class RenommageLu(LectureEnBase):
    """Collection « veille » devenue « watch », vue par la lecture du serveur : aucun alias, le nom stocké est celui qu'on voit (sautée sans base)."""

    def setUp(self):
        super().setUp()
        self.indexer()

    def stocke(self, livre: str, *noms: str) -> None:
        """Remet les collections du livre dans la base, sous ces noms stockés."""
        magasin = self.magasin()
        magasin.open()
        try:
            magasin.set_collections({livre: frozenset(noms)})
        finally:
            magasin.close()

    def test_ancien_index_montre_le_nom_stocke_et_le_nom_actuel_ne_trouve_rien(self):
        self.stocke("article-flux.md", "veille")
        biblio = self.bibliotheque()
        self.assertEqual(biblio.collections().get("veille"), 1)
        self.assertNotIn("watch", biblio.collections())
        self.assertEqual(biblio.search("métriques de flux agrégées", ["watch"], 5), [])
        self.assertFalse(hasattr(biblio, "stored_aliases"))
        self.assertFalse(hasattr(library, "COLLECTION_ALIASES"))

    def test_nouvel_index_ne_trouve_rien_par_l_ancien_nom(self):
        biblio = self.bibliotheque()
        self.assertEqual(biblio.search("métriques de flux agrégées", ["veille"], 5), [])
        hits = biblio.search("métriques de flux agrégées", ["watch"], 5)
        self.assertEqual({h["file"] for h in hits}, {"article-flux.md"})

    def test_les_deux_noms_stockes_restent_distincts(self):
        self.stocke("article-flux.md", "veille")
        self.stocke("Flux.md", "watch")
        biblio = self.bibliotheque()
        self.assertEqual(biblio.collections()["watch"], 1)
        self.assertEqual(biblio.collections()["veille"], 1)
        hits = biblio.search("flux cycle time débit", ["watch"], 10)
        self.assertEqual({h["file"] for h in hits}, {"Flux.md"})


class Gardes(Base):
    """Gardes d'une indexation (design.md D1 étapes 2, 3, 5 ; D2) : base injoignable, verrou tenu, dossiers vides."""

    def lancer(self, *arguments, **options):
        sortie, erreurs = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreurs):
            try:
                if arguments:
                    with mock.patch.object(sys, "argv", ["pmzilla_lab_library.py", *arguments]):
                        library.main(store=self.store)
                else:
                    library.index([self.racine], store=self.store, **options)
            except SystemExit as arret:
                code, message = code_de_sortie(arret), arret.code
                if isinstance(message, str):
                    erreurs.write(message)
        return code, sortie.getvalue() + erreurs.getvalue()

    def vider_les_dossiers(self):
        shutil.rmtree(self.racine)
        (self.racine / "flow").mkdir(parents=True)

    def test_base_injoignable_code_2_sans_appel_au_modele(self):
        self.store = FakeStore(available=False)
        code, sortie = self.lancer()
        self.assertEqual(code, 2)
        self.assertIn("Database unreachable: nothing was indexed. Start it: bash tools/db_up.sh", sortie)
        self.assertEqual(self.calls, 0)
        for interdit in ("password", "postgresql://", "OperationalError"):
            self.assertNotIn(interdit, sortie)

    def test_verrou_tenu_code_1_rien_n_est_ecrit(self):
        self.store = FakeStore(locked=True)
        code, sortie = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn("Another indexing run is in progress: nothing was indexed.", sortie)
        self.assertEqual((self.store.writes, self.calls), ([], 0))
        self.assertEqual(self.store.closed, 1)                           # la connexion est rendue

    def test_dossiers_vides_face_a_une_base_remplie_refuses(self):
        self.indexer()
        self.vider_les_dossiers()
        ecritures = list(self.store.writes)
        code, sortie = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn("No book found in the folders while the database holds 4: nothing was removed "
                      "(--allow-empty empties the library).", sortie)
        self.assertEqual(len(self.store.books), 4)
        self.assertEqual(self.store.writes, ecritures)
        self.assertNotIn("removed:", sortie)

    def test_allow_empty_vide_la_bibliotheque_en_nommant_chaque_livre(self):
        self.indexer()
        self.vider_les_dossiers()
        code, sortie = self.lancer(allow_empty=True)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.store.books, {})
        for nom in ("Flux.md", "Discovery.md", "Topologies.md", "article-flux.md"):
            self.assertIn(f"removed: {nom}", sortie)

    def test_allow_empty_en_ligne_de_commande(self):
        self.indexer()
        self.vider_les_dossiers()
        code, sortie = self.lancer("index", str(self.racine))
        self.assertEqual(code, 1)
        self.assertEqual(len(self.store.books), 4)
        code, sortie = self.lancer("index", "--allow-empty", str(self.racine))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.store.books, {})

    def test_base_vide_et_dossiers_vides_sans_option(self):
        self.vider_les_dossiers()
        code, sortie = self.lancer()
        self.assertEqual(code, 0, sortie)
        self.assertIn("Indexed: 0 · unchanged: 0", sortie)


class AvecBase(LectureEnBase):
    """KnowledgeStore sur une base jetable migrée (tests/library_backend/pg_demo.py), tables knowledge vidées avant chaque test.
    Sautée sans base ; lancée par l'utilisateur avec bash tools/dbtest.sh. Jamais la vraie base."""

    def test_premiere_indexation_puis_relance_inchangee(self):
        self.assertIn("Indexed: 4 · unchanged: 0", self.indexer())
        self.assertEqual(self.valeur("SELECT count(*) FROM knowledge.books"), 4)
        self.assertEqual({r[0] for r in self.lecture.execute("SELECT name FROM knowledge.collections")},
                         {"flow", "produit", "organisation", "watch"})
        self.assertEqual({r[0] for r in self.lecture.execute("SELECT DISTINCT kind FROM knowledge.chunks")}, {"text"})
        meta = self.valeur("SELECT meta FROM knowledge.books WHERE file_name = 'article-flux.md'")
        self.assertEqual(meta["url"], "https://exemple.test/a")
        appels = self.calls
        self.assertIn("Indexed: 0 · unchanged: 4", self.indexer())
        self.assertEqual(self.calls, appels)
        self.assertEqual(self.fichiers_sqlite(), [])

    def test_vecteur_en_demi_precision(self):
        self.indexer()
        section, texte, vecteur = self.lecture.execute(
            "SELECT c.section, c.text, c.embedding::text FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id "
            "WHERE b.file_name = 'Flux.md' ORDER BY c.position LIMIT 1").fetchone()
        attendu = fake_embed_1024([f"Flux inventé\n{section}\n{texte}"])[0].astype(np.float16)
        lu = np.array([float(v) for v in vecteur.strip()[1:-1].split(",")], dtype=np.float32).astype(np.float16)
        self.assertEqual(lu.tobytes(), attendu.tobytes())

    def test_livre_reecrit_remplace_et_mot_disparu_introuvable(self):
        self.indexer()
        requete = "SELECT count(*) FROM knowledge.chunks WHERE search_vector @@ to_tsquery('simple', %s)"
        self.assertGreater(self.valeur(requete, ("kanban",)), 0)
        self.ecrire("flow/Flux.md", livre("Flux inventé", {
            "Seule section": "Texte entièrement nouveau sur la loi de Little et les files d'attente, "
                             "assez long pour dépasser le seuil de quatre-vingts caractères."}))
        self.assertIn("Indexed: 1 · unchanged: 3", self.indexer())
        self.assertEqual(self.valeur(requete, ("kanban",)), 0)
        self.assertGreater(self.valeur(requete, ("little",)), 0)

    def test_fichier_supprime_sort_avec_ses_passages(self):
        self.indexer()
        (self.racine / "produit" / "Discovery.md").unlink()
        self.assertIn("removed: Discovery.md", self.indexer())
        self.assertEqual(self.valeur("SELECT count(*) FROM knowledge.books WHERE file_name = 'Discovery.md'"), 0)
        self.assertEqual(self.valeur("SELECT count(*) FROM knowledge.chunks WHERE text LIKE %s", ("%arbre d'opportunités%",)), 0)

    def test_livre_en_echec_ne_laisse_ni_livre_ni_passage(self):
        def plongement(texts):
            out = fake_embed_1024(texts)
            if any(t.startswith("Discovery inventée") for t in texts):
                out[:] = np.nan                                  # refusé par halfvec : l'écriture du livre échoue
            return out
        self.plongement = plongement
        with self.assertRaises(SystemExit) as arret, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            library.index([self.racine], store=self.store)
        self.assertEqual(code_de_sortie(arret.exception), 1)
        self.assertIn("Discovery.md", str(arret.exception.code))
        self.assertEqual({r[0] for r in self.lecture.execute("SELECT file_name FROM knowledge.books")},
                         {"Flux.md", "Topologies.md", "article-flux.md"})
        self.assertEqual(self.valeur("SELECT count(*) FROM knowledge.chunks c WHERE NOT EXISTS "
                                     "(SELECT 1 FROM knowledge.books b WHERE b.id = c.book_id)"), 0)

    def test_collection_orpheline_supprimee(self):
        self.indexer()
        appels = self.calls
        shutil.move(self.racine / "produit" / "Discovery.md", self.racine / "organisation" / "Discovery.md")
        self.indexer()
        self.assertEqual(self.calls, appels)
        self.assertEqual(self.valeur("SELECT count(*) FROM knowledge.collections WHERE name = 'produit'"), 0)

    def test_deuxieme_indexation_refusee_tant_que_la_premiere_tient_le_verrou(self):
        premiere = self.magasin()
        premiere.open()
        self.addCleanup(premiere.close)
        self.assertTrue(premiere.try_lock())
        with self.assertRaises(SystemExit) as arret, contextlib.redirect_stdout(io.StringIO()):
            library.index([self.racine], store=self.store)
        self.assertEqual(code_de_sortie(arret.exception), 1)
        self.assertIn("Another indexing run is in progress", str(arret.exception.code))
        self.assertEqual((self.valeur("SELECT count(*) FROM knowledge.books"), self.calls), (0, 0))
        premiere.close()                                          # verrou rendu : la suivante passe
        self.assertIn("Indexed: 4", self.indexer())

    def test_renommage_en_une_transaction_sans_toucher_les_vecteurs(self):
        self.indexer()
        appels = self.calls
        self.lecture.execute("INSERT INTO knowledge.collections (name) VALUES ('veille')")
        self.lecture.execute(
            "UPDATE knowledge.book_collections SET collection_id = (SELECT id FROM knowledge.collections WHERE name = 'veille') "
            "WHERE book_id = (SELECT id FROM knowledge.books WHERE file_name = 'article-flux.md')")
        self.lecture.execute("DELETE FROM knowledge.collections WHERE name = 'watch'")
        avant = self.lecture.execute("SELECT id, book_id, position, text, embedding::text FROM knowledge.chunks ORDER BY id").fetchall()

        def renommer(*args):
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                library.rename_collection(*args, store=self.magasin())
            return sortie.getvalue()

        self.assertIn("would be renamed", renommer("veille", "watch", True))
        self.assertEqual(self.valeur("SELECT count(*) FROM knowledge.collections WHERE name = 'veille'"), 1)
        self.assertIn("1 books", renommer("veille", "watch"))
        noms = self.valeur(
            "SELECT array_agg(c.name) FROM knowledge.book_collections bc JOIN knowledge.collections c ON c.id = bc.collection_id "
            "JOIN knowledge.books b ON b.id = bc.book_id WHERE b.file_name = 'article-flux.md'")
        self.assertEqual(noms, ["watch"])
        self.assertEqual(self.valeur("SELECT count(*) FROM knowledge.collections WHERE name = 'veille'"), 0)
        self.assertEqual(self.lecture.execute(
            "SELECT id, book_id, position, text, embedding::text FROM knowledge.chunks ORDER BY id").fetchall(), avant)
        self.assertIn("nothing to do", renommer("veille", "watch"))
        self.assertEqual(self.calls, appels)                      # aucun appel au modèle par le renommage


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
