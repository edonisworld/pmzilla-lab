"""
Tests de tools/hybrid_search.py (recherche hybride SQL du lot 4) sur la bibliothèque inventée.

    bash tests/run_all.sh hybrid_search

Sans base : la fusion et le bonus de fraîcheur en Python pur sont comparés à la voie SQLite (`Library.search`), et la requête SQL
est inspectée (paramètres, absence d'interpolation, balayage exact ou ANN) avec une fausse connexion. Avec une base jetable
(sautés si elle manque) : la requête SQL est jouée sur les mêmes données et comparée à la voie SQLite. Aucun appel à Ollama.
"""
import datetime as dt
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
import pg_demo                  # noqa: E402  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import demo_library as demo     # noqa: E402
import hybrid_search as hs      # noqa: E402
import watch_paths              # noqa: E402
import pmzilla_lab_library as library  # noqa: E402

TODAY = dt.date.today()


class Sqlite(unittest.TestCase):
    """Une vraie `Library` SQLite sur la bibliothèque inventée, embedding remplacé."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        chemin = Path(self.tmp.name) / "library.sqlite"
        demo.build_sqlite(chemin)
        for patch in (mock.patch.object(library, "DATA_DIR", Path(self.tmp.name)), mock.patch.object(library, "DB_PATH", chemin),
                      mock.patch.object(library, "embed", demo.fake_embed)):
            patch.start()
            self.addCleanup(patch.stop)
        self.lib = library.Library()


class Constantes(unittest.TestCase):
    def test_memes_constantes_que_la_voie_sqlite(self):
        self.assertEqual(hs.RRF_K, library.RRF_K)
        self.assertEqual(hs.CANDIDATES, library.CANDIDATES)
        self.assertEqual(hs.FRESHNESS_HALF_LIFE, library.FRESHNESS_HALF_LIFE)
        self.assertEqual(hs.FRESHNESS_BONUS, library.FRESHNESS_BONUS)
        self.assertEqual(set(hs.FRESHNESS_COLLECTIONS), library.FRESHNESS_COLLECTIONS)

    def test_nom_de_la_collection_personnelle(self):
        nom = hs.OWN_COLLECTION
        self.assertRegex(nom, r"^[a-z][a-z0-9-]*$")
        self.assertNotIn(nom, ("watch", "veille"))
        self.assertEqual(nom, watch_paths.OWN_COLLECTION)
        self.assertEqual(nom, library.OWN_COLLECTION)
        sql = hs.build_query(hs.LIBRARY_SPEC, query="le flux", vector=[0.5, 0.25], today=TODAY)[0]
        self.assertIn("'" + nom + "' = ANY(", sql)

    def test_mots_comme_la_voie_sqlite(self):
        self.assertEqual(hs.words("Le flux, l'équipe et l'état-de-l'art !"), ["Le", "flux", "l", "équipe", "et", "l", "état", "de", "l", "art"])
        self.assertEqual(hs.words("  ?! "), [])


class FusionEtFraicheur(Sqlite):
    def test_bonus_de_fraicheur_identique_a_la_voie_sqlite(self):
        lib = self.lib
        lib.refresh()
        for chunk_id, (collections, published) in lib.chunk_info.items():
            attendu = lib._freshness(chunk_id, TODAY)
            self.assertAlmostEqual(hs.freshness_bonus(published, collections, TODAY), attendu, places=12, msg=chunk_id)

    def test_bonus_cas_limites(self):
        self.assertEqual(hs.freshness_bonus(None, {"watch"}, TODAY), hs.FRESHNESS_BONUS / 2)
        self.assertEqual(hs.freshness_bonus("2026-01-01", {"produit"}, TODAY), hs.FRESHNESS_BONUS / 2)
        self.assertEqual(hs.freshness_bonus((TODAY).isoformat(), {"watch", hs.OWN_COLLECTION}, TODAY), hs.FRESHNESS_BONUS / 2)
        self.assertEqual(hs.freshness_bonus("pas-une-date", {"watch"}, TODAY), hs.FRESHNESS_BONUS / 2)
        self.assertAlmostEqual(hs.freshness_bonus(TODAY.isoformat(), {"watch"}, TODAY), hs.FRESHNESS_BONUS)
        self.assertAlmostEqual(hs.freshness_bonus((TODAY - dt.timedelta(days=180)).isoformat(), {"watch"}, TODAY), hs.FRESHNESS_BONUS / 2)

    def test_fusion_identique_a_library_search(self):
        lib = self.lib
        for question in ("le flux de travail", "hypothesis experiment", "prévisibilité du débit", "coaching", "équipe", "rien de connu"):
            with self.subTest(question=question):
                kinds = lib.check_types(None)
                allowed = lib._type_filter(kinds, lib._collection_filter(None))
                listes = [lib._semantic(question, allowed), lib._keyword(question, allowed, kinds)]
                reference = hs.fuse(listes, lambda cid: hs.freshness_bonus(lib.chunk_info[cid][1], lib.chunk_info[cid][0], TODAY),
                                    limit=14)
                voie_sqlite = lib.search(question, None, 14)
                self.assertEqual([i for i, _ in reference], [r["passage_id"] for r in voie_sqlite])
                self.assertEqual([round(s, 4) for _, s in reference], [r["score"] for r in voie_sqlite])

    def test_fusion_valeurs_a_la_main(self):
        # a est premier des deux listes, b seulement de la première : 1/61 + 1/61 contre 1/62
        sortie = hs.fuse([["a", "b"], ["a"]], lambda _: 0.0)
        self.assertEqual([i for i, _ in sortie], ["a", "b"])
        self.assertAlmostEqual(sortie[0][1], 2 / 61)
        self.assertAlmostEqual(sortie[1][1], 1 / 62)
        self.assertEqual(hs.fuse([], lambda _: 0.0), [])
        self.assertEqual(len(hs.fuse([["a", "b", "c"]], lambda _: 0.0, limit=2)), 2)


class DepartageEtNormalisation(unittest.TestCase):
    """Départage final aligné sur SQLite (ordre d'arrivée : vecteur d'abord, puis plein texte seul) et drapeau de normalisation réglable."""

    def requete(self, **options):
        return hs.build_query(hs.LIBRARY_SPEC, query="equipe", vector=demo.fake_embed(["equipe"])[0], today=TODAY, **options)[0]

    def test_ordre_final_rang_vectoriel_puis_plein_texte_puis_id(self):
        sql = self.requete()
        self.assertIn("ORDER BY score DESC, sem.rank ASC NULLS LAST, kw.rank ASC NULLS LAST, f.id", sql)
        self.assertIn("LEFT JOIN sem ON sem.id = f.id", sql)
        self.assertIn("LEFT JOIN kw ON kw.id = f.id", sql)

    def test_requete_de_production_et_diagnostic_classent_pareil(self):
        production, diagnostic = self.requete(), self.requete(diagnostic=True)
        self.assertEqual(production.split("ORDER BY score DESC")[1], diagnostic.split("ORDER BY score DESC")[1])
        self.assertNotIn("sem_score", production)
        self.assertIn("sem_score", diagnostic)

    def test_drapeau_de_normalisation_par_defaut_et_reglable(self):
        self.assertIn(f"q.tsq, {hs.NORMALISATION_RANG})::numeric", self.requete(fulltext="tsvector"))
        self.assertIn("q.tsq, 0)::numeric", self.requete(rank_norm=0, fulltext="tsvector"))
        self.assertIn("q.tsq, 1)::numeric", self.requete(rank_norm=1, fulltext="tsvector"))
        with self.assertRaises(ValueError):
            self.requete(rank_norm=7)
        self.assertNotIn("ts_rank_cd", self.requete())          # BM25 par défaut : le drapeau ne sert qu'à la voie tsvector

    def test_plein_texte_ou_de_mots_comme_fts5(self):
        sql = self.requete(fulltext="tsvector")
        self.assertIn("string_agg(quote_literal(", sql)
        self.assertIn("' | '", sql)                              # OU entre les mots, comme l'expression FTS5 « "a" OR "b" »
        for et in ("plainto_tsquery", "websearch_to_tsquery", "' & '"):
            self.assertNotIn(et, sql)
        bm25 = self.requete()
        self.assertIn("||| %(bm25_query)s", bm25)                # BM25 : disjonction de mots (au moins un), jamais la conjonction
        self.assertNotIn("&&&", bm25)

    def test_composantes_ne_fusionnent_qu_une_voie(self):
        self.assertIn("FROM (SELECT id, rank FROM sem UNION ALL SELECT id, rank FROM kw) u", self.requete())
        self.assertIn("FROM (SELECT id, rank FROM sem) u", self.requete(component="vector"))
        self.assertIn("FROM (SELECT id, rank FROM kw) u", self.requete(component="text"))
        with self.assertRaises(ValueError):
            self.requete(component="autre")

    def test_option_rank_norm_de_la_parite_aligne_sur_la_validation(self):
        import library_parity
        parser = library_parity.build_parser()
        for valeur in (0, 1, 2):                     # exactement les valeurs que build_query accepte
            self.assertEqual(parser.parse_args(["--rank-norm", str(valeur)]).rank_norm, valeur)
            self.assertIn(f"q.tsq, {valeur})::numeric", self.requete(rank_norm=valeur, fulltext="tsvector"))
        self.assertIsNone(parser.parse_args([]).rank_norm)
        with self.assertRaises(SystemExit):
            parser.parse_args(["--rank-norm", "3"])
        with self.assertRaises(ValueError):
            self.requete(rank_norm=3)


# ---------------------------------------------------------------------------
# Mots courants contre mot rare : le défaut que la parité a révélé sur les vraies données (ts_rank_cd ignore l'IDF)
# ---------------------------------------------------------------------------

COURANTS = "le la de et des un une"
LIVRES_IDF = {            # file_name -> [(position, texte)] ; 40 passages de bruit contiennent tous les mots courants (donc IDF quasi nul)
    "bruit.md": [(i, f"{COURANTS} passage de bruit numéro {i} sans intérêt") for i in range(40)],
    "mots-courants.md": [(0, " ".join(COURANTS.split() * 12) + " production")],
    "mot-rare.md": [(0, "le quokka de la production")],
}
QUESTION_IDF = "le la de et quokka"


def ajouter_livres_sqlite(dossier, livres):
    import sqlite3
    connexion = sqlite3.connect(Path(dossier) / "library.sqlite")
    for nom, passages in livres.items():
        livre = connexion.execute("INSERT INTO books (file_name, title, sha256, collections, model, indexed_at, meta) "
                                  "VALUES (?, ?, 'x', 'produit', 'bge-m3', 0, '{}')", (nom, nom)).lastrowid
        for position, texte in passages:
            connexion.execute("INSERT INTO chunks (book_id, position, section, text, embedding, kind, ref) VALUES (?, ?, 'Début', ?, ?, 'texte', '{}')",
                              (livre, position, texte, demo.chunk_blob(0.9)))
    connexion.commit()
    connexion.close()


class MotsCourantsContreMotRare(Sqlite):
    def test_reference_sqlite_le_mot_rare_passe_devant(self):
        ajouter_livres_sqlite(self.tmp.name, LIVRES_IDF)
        self.lib._load()
        premiers = [(r["file"], r["position"]) for r in self.lib.search(QUESTION_IDF, ["produit"], 3, None, None, component="text")]
        # (collection « produit » : sans les billets de la veille, dont le bonus de fraîcheur peut passer devant un rang d'écart)
        self.assertEqual(premiers[0], ("mot-rare.md", 0))              # BM25 : l'IDF du mot rare écrase les mots courants
        self.assertNotEqual(premiers[0], ("mots-courants.md", 0))      # le passage plein de mots courants ne passe pas devant


def _test_mot_rare_avant_mots_courants_sur_les_deux_voies(self):
    """Même corpus dans la base jetable : avec BM25 le passage qui contient le mot rare sort premier, comme sur la voie SQLite."""
    ajouter_livres_sqlite(self.tmp.name, LIVRES_IDF)
    self.lib._load()
    brut = self.pg._raw()
    brut.execute("SET ROLE pmzilla_knowledge")
    collection = brut.execute("SELECT id FROM knowledge.collections WHERE name = 'produit'").fetchone()[0]
    for nom, passages in LIVRES_IDF.items():
        livre = brut.execute("INSERT INTO knowledge.books (file_name, title, meta, sha256, model, indexed_at) VALUES (%s, %s, '{}'::jsonb, 'x', 'bge-m3', now()) RETURNING id",
                             (nom, nom)).fetchone()[0]
        brut.execute("INSERT INTO knowledge.book_collections VALUES (%s, %s)", (livre, collection))
        for position, texte in passages:
            brut.execute("INSERT INTO knowledge.chunks (book_id, position, section, text, embedding) VALUES (%s, %s, 'Début', %s, %s::halfvec)",
                         (livre, position, texte, pg_demo.literal_of(demo.vector(0.9))))
    brut.execute("RESET ROLE")
    brut.commit()
    rows = self.conn.execute("SELECT c.id, b.file_name, c.position FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id").fetchall()
    self.conn.rollback()
    self.cle_pg = {r[0]: (r[1], r[2]) for r in rows}
    bm25, _ = self.pg_search(QUESTION_IDF, limit=5, kinds=["text"], collections=["produit"], component="text", fulltext="bm25")
    attendu = [(r["file"], r["position"]) for r in self.lib.search(QUESTION_IDF, ["produit"], 5, None, None, component="text")]
    self.assertEqual(bm25[0], ("mot-rare.md", 0))
    self.assertEqual(attendu[0], ("mot-rare.md", 0))
    self.assertEqual(bm25[0], attendu[0])


class VecteursDegeneres(Sqlite):
    """Cause trouvée par la parité sur les vraies données : la voie SQLite classe au produit scalaire (numpy, sans renormaliser) ; un cosinus SQL
    range un vecteur nul (NaN) avant tous les autres en tri décroissant. Un vecteur nul et un vecteur de norme 2 l'auraient montré."""

    def ajouter_degeneres(self):
        import sqlite3
        chemin = Path(self.tmp.name) / "library.sqlite"
        connexion = sqlite3.connect(chemin)
        livre = connexion.execute("INSERT INTO books (file_name, title, sha256, collections, model, indexed_at, meta) "
                                  "VALUES ('degenere.md', 'Livre dégénéré', 'x', 'produit', 'bge-m3', 0, '{}')").lastrowid
        for position, vecteur in ((0, demo.np.zeros(demo.DIMENSIONS, dtype=demo.np.float32)), (1, 2 * demo.vector(0.22))):
            connexion.execute("INSERT INTO chunks (book_id, position, section, text, embedding, kind, ref) VALUES (?, ?, 'Début', 'texte neutre', ?, 'texte', '{}')",
                              (livre, position, vecteur.astype(demo.np.float16).tobytes()))
        connexion.commit()
        connexion.close()
        self.lib._load()
        return livre

    def test_la_voie_sqlite_est_un_produit_scalaire(self):
        self.ajouter_degeneres()
        classement = self.lib._semantic("flux", None)           # fake_embed : angle 0,22
        premier = self.lib.db.execute("SELECT b.file_name, c.position FROM chunks c JOIN books b ON b.id = c.book_id WHERE c.id = ?",
                                      (classement[0],)).fetchone()
        self.assertEqual(tuple(premier), ("degenere.md", 1))      # norme 2 : produit scalaire double ; un cosinus l'aurait mis à égalité
        zero = self.lib.db.execute("SELECT c.id FROM chunks c JOIN books b ON b.id = c.book_id WHERE b.file_name = 'degenere.md' AND c.position = 0").fetchone()[0]
        self.assertNotEqual(classement[0], zero)                  # un vecteur nul vaut 0 : il ne passe jamais devant
        self.assertGreater(classement.index(zero), 5)

    def test_le_bonus_de_fraicheur_peut_depasser_un_rang_sur_la_voie_sqlite_aussi(self):
        """Pourquoi les comparaisons du vecteur seul se font dans une collection sans billets : le billet récent (même angle que la question, produit
        scalaire 1, rang 1) passe devant le vecteur de norme 2 (produit scalaire 2, rang 0), à cause du bonus de fraîcheur. Même comportement des deux voies."""
        self.ajouter_degeneres()
        sans_filtre = [(r["file"], r["position"]) for r in self.lib.search("flux", None, 3, None, None, component="vector")]
        self.assertEqual(sans_filtre[0], ("billet-recent.md", 0))
        produit = [(r["file"], r["position"]) for r in self.lib.search("flux", ["produit"], 3, None, None, component="vector")]
        self.assertEqual(produit[0], ("degenere.md", 1))


def _test_vecteur_nul_et_non_normalise_comme_sqlite(self):
    """Même jeu dans la base jetable : la requête SQL doit classer le vecteur nul et le vecteur de norme 2 comme SQLite (composante vecteur seule)."""
    import sqlite3
    chemin = Path(self.tmp.name) / "library.sqlite"
    connexion = sqlite3.connect(chemin)
    livre = connexion.execute("INSERT INTO books (file_name, title, sha256, collections, model, indexed_at, meta) "
                              "VALUES ('degenere.md', 'Livre dégénéré', 'x', 'produit', 'bge-m3', 0, '{}')").lastrowid
    vecteurs = ((0, demo.np.zeros(demo.DIMENSIONS, dtype=demo.np.float32)), (1, 2 * demo.vector(0.22)))
    for position, vecteur in vecteurs:
        connexion.execute("INSERT INTO chunks (book_id, position, section, text, embedding, kind, ref) VALUES (?, ?, 'Début', 'texte neutre', ?, 'texte', '{}')",
                          (livre, position, vecteur.astype(demo.np.float16).tobytes()))
    connexion.commit()
    connexion.close()
    self.lib._load()
    brut = self.pg._raw()
    brut.execute("SET ROLE pmzilla_knowledge")
    livre_pg = brut.execute("INSERT INTO knowledge.books (file_name, title, meta, sha256, model, indexed_at) VALUES ('degenere.md', 'Livre dégénéré', '{}'::jsonb, 'x', 'bge-m3', now()) RETURNING id").fetchone()[0]
    collection = brut.execute("SELECT id FROM knowledge.collections WHERE name = 'produit'").fetchone()[0]
    brut.execute("INSERT INTO knowledge.book_collections VALUES (%s, %s)", (livre_pg, collection))
    for position, vecteur in vecteurs:
        brut.execute("INSERT INTO knowledge.chunks (book_id, position, section, text, embedding) VALUES (%s, %s, 'Début', 'texte neutre', %s::halfvec)",
                     (livre_pg, position, pg_demo.literal_of(vecteur)))
    brut.execute("RESET ROLE")
    brut.commit()
    rows = self.conn.execute("SELECT c.id, b.file_name, c.position FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id").fetchall()
    self.conn.rollback()
    self.cle_pg = {r[0]: (r[1], r[2]) for r in rows}
    # collection « produit » : sans les billets de la veille, dont le bonus de fraîcheur (0,001 contre 0,0005) vaut plus qu'un rang d'écart de la
    # fusion (1/61 - 1/62 = 0,00026) et fait passer un billet récent devant le premier de la liste vectorielle, sur les DEUX voies
    cles, _ = self.pg_search("flux", limit=6, kinds=["text"], collections=["produit"], component="vector")
    attendu = [(r["file"], r["position"]) for r in self.lib.search("flux", ["produit"], 6, None, None, component="vector")]
    self.assertEqual(cles[0], ("degenere.md", 1))
    self.assertEqual(cles, attendu)
    self.assertNotEqual(cles[0], ("degenere.md", 0))


def _test_requete_a_plusieurs_mots_est_un_ou(self):
    """Le plein texte de SQLite est un OU de mots : trois mots dont aucun passage ne réunit les trois donnent l'union, pas rien (un ET)."""
    question = "équipe prévisibilité débit"
    cles, _ = self.pg_search(question, limit=14, kinds=["text"], component="text")
    attendu = {(r["file"], r["position"]) for r in self.lib.search(question, None, 14, None, None, component="text")}
    self.assertGreaterEqual(len(attendu), 3)
    self.assertEqual(set(cles), attendu)




class FausseConnexion:
    def __init__(self):
        self.executed, self.rolled_back = [], 0

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return [(7, 0.0333), (3, 0.0161)]

    def rollback(self):
        self.rolled_back += 1


class Requete(unittest.TestCase):
    def build(self, **options):
        return hs.build_query(hs.LIBRARY_SPEC, query=options.pop("query", "le flux"), vector=[0.5, 0.25], today=TODAY, **options)

    def test_aucune_valeur_dans_le_sql(self):
        hostile = "x'); DROP TABLE knowledge.books; --"
        sql, params = self.build(query=hostile, collections=["flow"], since="2026-01-01", kinds=["text"])
        self.assertNotIn("DROP", sql)
        self.assertNotIn("2026-01-01", sql)
        self.assertNotIn("0.25", sql)
        self.assertEqual(set(params), {"words", "qvec", "today", "collections", "since", "kinds", "bm25_query"})
        self.assertEqual(params["words"], ["x", "DROP", "TABLE", "knowledge", "books"])
        self.assertEqual(params["collections"], ["flow"])
        self.assertEqual(params["qvec"], "[0.5,0.25]")
        self.assertEqual(params["today"], TODAY.isoformat())

    def test_filtres_seulement_si_demandes(self):
        sql, params = self.build()
        for texte in ("%(collections)s", "%(since)s", "%(kinds)s"):
            self.assertNotIn(texte, sql)
        self.assertEqual(set(params), {"words", "qvec", "today", "bm25_query"})
        sql, _ = self.build(collections=["flow"])
        self.assertIn("%(collections)s", sql)
        sql, _ = self.build(since="2026-01-01")
        self.assertIn("published_on IS NULL OR b.published_on >= %(since)s", sql)       # un livre sans date est gardé
        sql, _ = self.build(kinds=["figure"])
        self.assertIn("c.kind = ANY(%(kinds)s::text[])", sql)

    def test_constantes_de_la_fusion_dans_le_sql(self):
        sql, _ = self.build(limit=5, fulltext="tsvector")
        self.assertIn("60 + rank + 1", sql)
        self.assertIn("rank < 50", sql)
        self.assertIn("LIMIT 5", sql)
        self.assertIn("'simple'", sql)
        self.assertIn("knowledge.immutable_unaccent(lower(w))", sql)
        self.assertIn("ts_rank_cd", sql)
        self.assertIn(f"q.tsq, {hs.NORMALISATION_RANG})", sql)       # normalisé par la longueur, comme la pénalité des passages longs de BM25
        self.assertEqual(hs.NORMALISATION_RANG, 1)
        self.assertIn("round(score::numeric, 3) DESC, fresh DESC, id", sql)

    def test_balayage_exact_ou_ann(self):
        exact, _ = self.build(scan="exact")
        self.assertIn("-(vec::vector <#> %(qvec)s::vector) AS score", exact)       # produit scalaire, comme numpy (pas le cosinus)
        self.assertNotIn("<=> %(qvec)s::vector", exact)
        self.assertNotIn("halfvec", exact.replace("embedding", ""))
        self.assertIn("WITH scope AS NOT MATERIALIZED", exact)      # jamais matérialisée : sinon tous les passages seraient recopiés à chaque requête
        ann, _ = self.build(scan="ann")
        self.assertIn("ORDER BY vec <=> %(qvec)s::halfvec LIMIT 50", ann)       # l'index HNSW ordonne les candidats au cosinus
        self.assertIn("-(vec <#> %(qvec)s::halfvec) AS score", ann)               # le score reste le produit scalaire
        self.assertIn("NOT MATERIALIZED", ann)

    def test_bm25_par_defaut_et_options_inconnues(self):
        sql, params = self.build()
        self.assertIn("pdb.score(c.id)", sql)
        self.assertIn("c.fts_text ||| %(bm25_query)s", sql)                    # OU de mots, tokenisés comme l'index
        self.assertIn("LIMIT 200", sql)                                         # 4 x 50 meilleurs d'abord, comme la voie SQLite
        self.assertNotIn("ts_rank_cd", sql)
        self.assertEqual(params["bm25_query"], "le flux")
        with self.assertRaises(ValueError):
            self.build(scan="autre")
        with self.assertRaises(ValueError):
            self.build(fulltext="autre")

    def hits_de(self, **options):
        sql, _ = self.build(**options)
        return sql.split("hits AS (")[1].split("kw AS (")[0]

    def test_bm25_filtre_type_collection_et_date_avant_la_limite(self):
        sql, _ = self.build(collections=["flow"], since="2026-01-01", kinds=["text"])
        hits = sql.split("hits AS (")[1].split("kw AS (")[0]
        avant_limite = hits.split("LIMIT")[0]
        self.assertIn("c.kind = ANY(%(kinds)s::text[])", avant_limite)           # le type de passage, comme `chunks.kind IN (...)` de FTS5
        self.assertIn("c.book_id IN (SELECT b.id FROM knowledge.books b WHERE", avant_limite)       # la liste des livres retenus (option 3)
        self.assertIn("%(collections)s", avant_limite)                           # la collection, AVANT la limite de 200
        self.assertIn("b.published_on IS NULL OR b.published_on >= %(since)s", avant_limite)       # la date aussi, un livre sans date est gardé
        self.assertIn("LIMIT 200", hits)
        self.assertIn("FROM hits h JOIN scope s ON s.id = h.id", sql)
        self.assertIn("%(collections)s", sql.split("kw AS (")[0].split("WITH scope")[1])      # `scope` garde ses filtres pour les autres voies
        depuis = hits.split("FROM ")[1].split("\n")[0]
        self.assertEqual(depuis.strip(), "knowledge.chunks c")                     # une seule table dans le FROM de `hits` : le classement reste poussé dans l'index

    def test_bm25_sans_filtre_de_collection_ni_de_date_requete_inchangee(self):
        hits = self.hits_de(kinds=["text"])
        self.assertEqual(hits, """
    SELECT c.id AS id, pdb.score(c.id) AS raw
    FROM knowledge.chunks c
    WHERE c.fts_text ||| %(bm25_query)s AND c.kind = ANY(%(kinds)s::text[])
    ORDER BY pdb.score(c.id) DESC
    LIMIT 200
),
""")                                                                          # le texte exact d'avant le change
        self.assertEqual(hits, self.hits_de(kinds=["text"], collections=None, since=None))
        self.assertNotIn("book_id", self.hits_de())

    def test_bm25_date_seule_avant_la_limite(self):
        avant_limite = self.hits_de(since="2026-01-01").split("LIMIT")[0]
        self.assertIn("c.book_id IN (SELECT b.id", avant_limite)
        self.assertIn("%(since)s", avant_limite)
        self.assertNotIn("%(collections)s", avant_limite)

    def test_bm25_collection_seule_sans_condition_de_date(self):
        avant_limite = self.hits_de(collections=["flow"]).split("LIMIT")[0]
        self.assertIn("%(collections)s", avant_limite)
        self.assertNotIn("%(since)s", avant_limite)

    def test_bm25_specification_sans_restriction_par_livre_filtre_apres_la_limite(self):
        spec = hs.HybridSpec(from_sql="cases.cases c", id_expr="c.id", vector_expr="c.embedding", collection_filter="TRUE OR %(collections)s::text[] IS NULL",
                             bm25_table_sql="cases.cases c", bm25_text_expr="c.fts_text", bm25_id_expr="c.id")
        sql, _ = hs.build_query(spec, query="abc", vector=[1.0], collections=["x"], today=TODAY)
        hits = sql.split("hits AS (")[1].split("kw AS (")[0]
        self.assertNotIn("%(collections)s", hits)                                  # inchangé pour les spécifications des cas et des expériences
        self.assertIn("%(collections)s", sql.split("kw AS (")[0].split("WITH scope")[1])

    def test_bm25_question_sans_mot_utilisable(self):
        sql, params = self.build(query=" ?! ")
        self.assertIn("WHERE FALSE", sql)
        self.assertEqual(params["bm25_query"], "")

    def test_composante_vecteur_sans_la_voie_texte_et_inversement(self):
        vecteur = self.build(component="vector")[0]
        texte = self.build(component="text")[0]
        self.assertIn("LEFT JOIN sem", vecteur)
        self.assertNotIn("LEFT JOIN kw", vecteur)                               # une voie non utilisée n'est pas évaluée
        self.assertIn("LEFT JOIN kw", texte)
        self.assertNotIn("LEFT JOIN sem", texte)

    def test_specification_sans_fraicheur_ni_filtre(self):
        spec = hs.HybridSpec(from_sql="cases.cases k", id_expr="k.id", vector_expr="k.embedding", tsvector_expr="k.search_vector")
        with self.assertRaises(ValueError):                                       # BM25 par défaut : une spécification sans index BM25 est refusée
            hs.build_query(spec, query="abc", vector=[1.0], today=TODAY)
        sql, params = hs.build_query(spec, query="abc", vector=[1.0], collections=["x"], since="2026-01-01", kinds=["a"], today=TODAY,
                                     fulltext="tsvector")
        self.assertNotIn("%(collections)s", sql)       # pas de filtre déclaré : ignoré, jamais de colonne inventée
        self.assertNotIn("power(", sql)
        self.assertIn("FROM cases.cases k", sql)
        self.assertNotIn("collections", params)

    def test_execution_lit_et_ferme_la_transaction(self):
        conn = FausseConnexion()
        trouves = hs.hybrid_search(conn, hs.LIBRARY_SPEC, query="le flux", vector=[0.5, 0.25], limit=2, today=TODAY, scan="exact")
        self.assertEqual(trouves, [(7, 0.0333), (3, 0.0161)])
        self.assertEqual(len(conn.executed), 1)
        self.assertEqual(conn.rolled_back, 1)

    def test_ann_regle_hnsw_dans_la_transaction(self):
        conn = FausseConnexion()
        hs.hybrid_search(conn, hs.LIBRARY_SPEC, query="le flux", vector=[0.5], scan="ann", ef_search=200, today=TODAY)
        self.assertEqual([s for s, _ in conn.executed[:2]], ["SET LOCAL hnsw.ef_search = 200", "SET LOCAL hnsw.iterative_scan = relaxed_order"])
        self.assertEqual(len(conn.executed), 3)

    def test_defaut_ann_et_400(self):
        self.assertEqual((hs.DEFAULT_SCAN, hs.EF_SEARCH), ("ann", 400))
        defaut, _ = self.build()
        self.assertIn("ORDER BY vec <=> %(qvec)s::halfvec LIMIT 50", defaut)

    def test_ann_ef_search_par_defaut_couvre_les_candidats(self):
        conn = FausseConnexion()
        hs.hybrid_search(conn, hs.LIBRARY_SPEC, query="le flux", vector=[0.5], scan="ann", today=TODAY)
        self.assertEqual(conn.executed[0][0], f"SET LOCAL hnsw.ef_search = {hs.EF_SEARCH}")
        self.assertGreaterEqual(hs.EF_SEARCH, hs.CANDIDATES)

    def test_ann_ef_search_hors_bornes(self):
        for valeur in (0, 1001):
            with self.assertRaises(ValueError):
                hs.hybrid_search(FausseConnexion(), hs.LIBRARY_SPEC, query="x", vector=[0.5], scan="ann", ef_search=valeur, today=TODAY)

    def test_vecteur_en_texte(self):
        self.assertEqual(hs.vector_literal([1, 0.5, -0.25]), "[1,0.5,-0.25]")


class AvecBase(Sqlite):
    """La requête SQL jouée sur les données inventées d'une base jetable (sautés sans base)."""

    def setUp(self):
        super().setUp()
        self.pg = pg_demo.ThrowawayDatabase(self)
        self.conn = self.pg.connect()
        rows = self.conn.execute("SELECT c.id, b.file_name, c.position FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id").fetchall()
        self.conn.rollback()
        self.cle_pg = {r[0]: (r[1], r[2]) for r in rows}

    def pg_search(self, question, **options):
        vecteur = demo.fake_embed([question])[0]
        found = hs.hybrid_search(self.conn, hs.LIBRARY_SPEC, query=question, vector=vecteur, today=TODAY, **options)
        return [self.cle_pg[i] for i, _ in found], [s for _, s in found]

    def sqlite_search(self, question, limit, collections=None, types=None, since=None):
        return [(r["file"], r["position"]) for r in self.lib.search(question, collections, limit, since, types)]

    def test_memes_resultats_que_la_voie_sqlite(self):
        for question in ("le flux de travail", "hypothesis experiment", "prévisibilité du débit", "coaching", "equipe"):
            with self.subTest(question=question):
                cles, _ = self.pg_search(question, limit=14, kinds=["text"])
                attendu = self.sqlite_search(question, 14)
                self.assertEqual(set(cles), set(attendu))
                self.assertEqual(cles[0], attendu[0])

    def test_accents_et_figures_et_collections_et_since(self):
        cles, _ = self.pg_search("equipe", limit=14, kinds=["text"])
        self.assertIn(("atelier-des-flux.md", 4), cles[:3])      # « équipe » trouvée par « equipe »
        figures, _ = self.pg_search("délai", limit=14, kinds=["figure"])
        self.assertEqual(sorted(figures), [("atelier-des-flux.md", 3), ("discovery-notes.md", 3)])
        watch, _ = self.pg_search("prévision", limit=14, collections=["watch"], kinds=["text"])
        self.assertEqual({f for f, _ in watch}, {"billet-recent.md", "billet-ancien.md", "article-propre.md"})
        recent, _ = self.pg_search("prévision", limit=14, kinds=["text"], since=(TODAY - dt.timedelta(days=5)).isoformat())
        self.assertNotIn("billet-ancien.md", {f for f, _ in recent})
        self.assertIn("atelier-des-flux.md", {f for f, _ in recent})      # un livre n'a pas de date : gardé

    def test_ann_donne_les_memes_resultats_sur_ce_petit_corpus(self):
        exact, _ = self.pg_search("le flux de travail", limit=8, kinds=["text"])
        ann, _ = self.pg_search("le flux de travail", limit=8, kinds=["text"], scan="ann")
        self.assertEqual(set(exact), set(ann))

    def test_question_sans_mot_utilisable(self):
        cles, _ = self.pg_search("?!", limit=5, kinds=["text"])
        self.assertEqual(len(cles), 5)       # le plein texte ne trouve rien, la sémantique répond


# ---------------------------------------------------------------------------
# Mode diagnostic (PMZILLA_DIAG=1) : affiche, sur le jeu inventé seulement, les valeurs intermédiaires des deux voies
#     PMZILLA_DIAG=1 PMZILLA_LAB_DB_PASSWORD=... python -m unittest tests/hybrid_search/test_hybrid_search.py -k diagnostic -v
# Aucune assertion : il ne sert qu'à lire l'écart entre la voie SQLite et la voie PostgreSQL.
# ---------------------------------------------------------------------------

import os   # noqa: E402

DIAGNOSTIC = os.environ.get("PMZILLA_DIAG") == "1"
QUESTION_DIAG = os.environ.get("PMZILLA_DIAG_QUERY", "equipe")


def _ligne(etiquette, cle, sem_rang, sem_score, kw_rang, kw_brut, rrf, frais, final):
    def nombre(v, fmt):
        return "      -" if v is None else format(v, fmt)
    return (f"  {etiquette}  {cle[0]}:{cle[1]:<2}  vecteur #{nombre(sem_rang, '>2')} score {nombre(sem_score, '.6f')}"
            f"  | plein texte #{nombre(kw_rang, '>2')} brut {nombre(kw_brut, '.6f')}"
            f"  | rrf {rrf:.12f} -> arrondi {round(rrf, 4):.4f}  | fraîcheur {frais:.6f}"
            f"  | final {final:.12f} -> arrondi {round(final, 4):.4f}")


def diagnostic_sqlite(lib, question):
    lib.refresh()
    cles = {r[0]: (r[1], r[2]) for r in lib.db.execute("SELECT c.id, b.file_name, c.position FROM chunks c JOIN books b ON b.id = c.book_id")}
    kinds = lib.check_types(None)
    allowed = lib._type_filter(kinds, lib._collection_filter(None))
    vecteur = demo.fake_embed([question])[0]
    scores = {int(i): float(s) for i, s in zip(lib.ids, lib.vectors @ vecteur)}
    sem = lib._semantic(question, allowed)
    kw = lib._keyword(question, allowed, kinds)
    expression = " OR ".join(f'"{m}"' for m in hs.words(question))
    marques = ", ".join("?" for _ in kinds)
    bruts = {r[0]: r[1] for r in lib.db.execute(
        "SELECT chunks_fts.rowid, bm25(chunks_fts) FROM chunks_fts JOIN chunks ON chunks.id = chunks_fts.rowid "
        f"WHERE chunks_fts MATCH ? AND chunks.kind IN ({marques})", (expression, *kinds))} if expression else {}
    rrf = {}
    for liste in (sem, kw):
        for rang, cid in enumerate(liste):
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (hs.RRF_K + rang + 1)
    finals = [r["passage_id"] for r in lib.search(question, None, 14)]
    lignes = []
    for cid in finals:
        frais = lib._freshness(cid, TODAY)
        lignes.append(_ligne("SQLite  ", cles[cid], sem.index(cid) if cid in sem else None, scores.get(cid),
                             kw.index(cid) if cid in kw else None, bruts.get(cid), rrf[cid], frais, rrf[cid] + frais))
    return lignes, [cles[c] for c in finals]


class DiagnosticSqlite(Sqlite):
    def test_diagnostic_voie_sqlite(self):
        if not DIAGNOSTIC:
            self.skipTest("PMZILLA_DIAG=1 pour afficher le diagnostic")
        if pg_demo.base.BASE_DISPONIBLE:
            self.skipTest("la base est disponible : le diagnostic des deux voies est affiché par AvecBase")
        lignes, ordre = diagnostic_sqlite(self.lib, QUESTION_DIAG)
        print(f"\n=== DIAGNOSTIC « {QUESTION_DIAG} » : voie SQLite seule (jeu inventé) ===")
        print("\n".join(lignes))
        print("  ordre final :", " > ".join(f"{f}:{p}" for f, p in ordre))


def _test_diagnostic_deux_voies(self):
    if True:
        if not DIAGNOSTIC:
            self.skipTest("PMZILLA_DIAG=1 pour afficher le diagnostic")
        question = QUESTION_DIAG
        lignes, ordre = diagnostic_sqlite(self.lib, question)
        vecteur = demo.fake_embed([question])[0]
        rows = hs.diagnose(self.conn, hs.LIBRARY_SPEC, query=question, vector=vecteur, limit=14, kinds=["text"], today=TODAY)
        print(f"\n=== DIAGNOSTIC « {question} » (jeu inventé, note : voie PostgreSQL limitée aux passages de texte) ===")
        print("-- voie SQLite : ordre final et valeurs intermédiaires")
        print("\n".join(lignes))
        print("  ordre final :", " > ".join(f"{f}:{p}" for f, p in ordre))
        print("-- voie PostgreSQL (ts_rank_cd normalisé drapeau", hs.NORMALISATION_RANG, ")")
        for r in rows:
            print(_ligne("Postgres", self.cle_pg[r["id"]], r["sem_rank"], r["sem_score"], r["kw_rank"], r["kw_raw"], r["rrf"], r["fresh"], r["score"]))
        print("  ordre final :", " > ".join(f"{self.cle_pg[r['id']][0]}:{self.cle_pg[r['id']][1]}" for r in rows))
        # un seul test d'égalité au niveau du RRF : où les deux voies divergent-elles ?
        sqlite_ids = [c for c in ordre]
        pg_ids = [self.cle_pg[r["id"]] for r in rows]
        premiere = next((i for i, (a, b) in enumerate(zip(sqlite_ids, pg_ids)) if a != b), None)
        print("  première divergence :", "aucune" if premiere is None else f"rang {premiere} : SQLite {sqlite_ids[premiere]} contre PostgreSQL {pg_ids[premiere]}")


AvecBase.test_diagnostic_deux_voies = _test_diagnostic_deux_voies      # une seule fois, dans AvecBase (pas de sous-classe : pas de doublon)
AvecBase.test_vecteur_nul_et_non_normalise_comme_sqlite = _test_vecteur_nul_et_non_normalise_comme_sqlite
AvecBase.test_requete_a_plusieurs_mots_est_un_ou = _test_requete_a_plusieurs_mots_est_un_ou
AvecBase.test_mot_rare_avant_mots_courants_sur_les_deux_voies = _test_mot_rare_avant_mots_courants_sur_les_deux_voies


if __name__ == "__main__":
    unittest.main()
