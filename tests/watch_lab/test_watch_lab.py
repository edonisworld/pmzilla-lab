"""
Tests de la collecte de la veille (tools/watch_lab.py) sur des flux et des pages inventés.

    uv run --with feedparser --with trafilatura --with httpx --with pyyaml --with beautifulsoup4 \
        --with markdownify python -m unittest discover -s tests/watch_lab -v

Aucun appel réseau : `veille.client` renvoie un client httpx branché sur un faux serveur (httpx.MockTransport)
qui répond aux flux RSS et aux pages inventés, et qui répond 404 à tout le reste ; les pauses de politesse sont
supprimées. Sources, état, articles et rapport sont dans un dossier temporaire : jamais Watch-Lab, watch/ ni
~/.pmzilla-lab.
"""
import argparse
import contextlib
import datetime as dt
import email.utils
import io
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import watch_lab as veille  # noqa: E402
import watch_paths  # noqa: E402

OWN = watch_paths.OWN_COLLECTION

AUJOURDHUI = dt.date.today()


def il_y_a(jours: int) -> str:
    jour = AUJOURDHUI - dt.timedelta(days=jours)
    return email.utils.format_datetime(dt.datetime(jour.year, jour.month, jour.day, 8, 0, tzinfo=dt.timezone.utc))


def paragraphes(n: int, sujet: str = "flux") -> str:
    """n paragraphes distincts (trafilatura supprime les répétitions), environ 70 caractères chacun."""
    return "".join(f"<p>Paragraphe numéro {i} inventé sur le {sujet} et la discovery produit en équipe.</p>"
                   for i in range(n))


def rss(items: list[dict], titre: str = "Blog inventé") -> bytes:
    corps = ""
    for item in items:
        corps += "<item>"
        corps += f"<title>{item['title']}</title>" if "title" in item else ""
        corps += f"<link>{item['link']}</link>" if "link" in item else ""
        corps += f"<pubDate>{item['date']}</pubDate>" if "date" in item else ""
        corps += f"<dc:creator>{item['author']}</dc:creator>" if "author" in item else ""
        corps += f"<category>{item['tag']}</category>" if "tag" in item else ""
        corps += f"<content:encoded><![CDATA[{item['html']}]]></content:encoded>" if "html" in item else ""
        corps += "</item>"
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" '
            f'xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"<channel><title>{titre}</title><link>https://blog.test</link>{corps}</channel></rss>").encode()


def page(corps_html: str, liens: str = "") -> bytes:
    return (f"<html><head><title>Page</title></head><body><nav><a href='https://menu.test/x'>menu</a></nav>"
            f"<article><h1>Titre</h1>{corps_html}{liens}</article></body></html>").encode()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = self.tmp / "Watch-Lab"
        self.routes: dict = {}
        self.requetes: list[str] = []

        def repondre(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            self.requetes.append(url)
            reponse = self.routes.get(url)
            if callable(reponse):
                reponse = reponse(request)
            if reponse is None:
                return httpx.Response(404, text="introuvable")
            if isinstance(reponse, bytes):
                return httpx.Response(200, content=reponse, headers={"content-type": "application/rss+xml"})
            return reponse

        self.faux_client = lambda: httpx.Client(transport=httpx.MockTransport(repondre), follow_redirects=True)
        for patch in (
            mock.patch.object(veille, "WATCH_DIR", self.dir),
            mock.patch.object(veille, "ARTICLES_DIR", self.dir / "watch"),
            mock.patch.object(veille, "SOURCES_FILE", self.tmp / "watch" / "sources.yaml"),
            mock.patch.object(veille, "STATE_DB", self.tmp / "data" / "veille.sqlite"),
            mock.patch.object(veille, "client", self.faux_client),
            mock.patch.object(veille.time, "sleep", lambda s: None),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def lancer(self, commande, **options) -> str:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            commande(argparse.Namespace(**options))
        return sortie.getvalue()

    def source(self, cle="blog.test", **reste):
        return {"key": cle, "name": "Blog inventé", "active": True, "feed": f"https://{cle}/feed", **reste}

    def activer(self, *sources):
        veille.save_sources(list(sources))

    def collecter(self, jours=30):
        return self.lancer(veille.cmd_collect, since_days=jours)

    def articles(self, dossier="watch"):
        return sorted((self.dir / dossier).glob("*.md")) if (self.dir / dossier).exists() else []

    def base(self):
        return sqlite3.connect(veille.STATE_DB)


class Fonctions(unittest.TestCase):
    def test_clean_url(self):
        self.assertEqual(veille.clean_url("HTTPS://www.Blog.test/post/?utm_source=x&id=2&fbclid=z#frag)."),
                         "https://blog.test/post?id=2")
        self.assertEqual(veille.clean_url("https://blog.test/"), "https://blog.test/")

    def test_source_of(self):
        self.assertEqual(veille.source_of("https://medium.com/@auteur/titre-123")["key"], "medium.com/@auteur")
        self.assertEqual(veille.source_of("https://medium.com/p/abc")["key"], "medium.com")
        self.assertEqual(veille.source_of("https://pub.medium.com/x")["feed"], "https://pub.medium.com/feed")
        self.assertEqual(veille.source_of("https://lettre.substack.com/p/x")["name"], "lettre")
        self.assertEqual(veille.source_of("https://www.blog.test/a/b")["key"], "blog.test")

    def test_slugify(self):
        self.assertEqual(veille.slugify("Été : l'équipe, déjà prête !", 60), "ete-l-equipe-deja-prete")
        self.assertEqual(veille.slugify("???", 10), "article")
        self.assertEqual(veille.slugify("a" * 50 + "-b", 20), "a" * 20)

    def test_keep_filtre_titre_et_categories(self):
        entree = {"title": "Discovery en pratique", "tags": [{"term": "Produit"}]}
        self.assertTrue(veille.keep(entree, {}))
        self.assertTrue(veille.keep(entree, {"include": ["produit"]}))
        self.assertFalse(veille.keep(entree, {"include": ["flux"]}))
        self.assertFalse(veille.keep(entree, {"exclude": ["DISCOVERY"]}))

    def test_html_to_markdown(self):
        texte = veille.html_to_markdown(
            "<h2>Titre</h2><script>alert(1)</script><p>Un <a href='x'>lien</a> utile.</p><img src='a.png'>"
            "<p>Continue reading on Medium</p>")
        self.assertIn("## Titre", texte)
        self.assertNotIn("alert", texte)
        self.assertNotIn("Continue reading", texte)
        self.assertIn("Un lien utile.", texte)

    def test_article_markdown(self):
        source = {"key": "blog.test", "name": 'Le "Blog"'}
        texte = veille.article_markdown('Un "titre"', "https://blog.test/a", source, "Auteur Inventé", "2026-10-01",
                                        "# Un \"titre\"\n\nCorps.", True)
        self.assertIn('title: "Un \'titre\' · Le \'Blog\'"', texte)
        self.assertIn("complete: true", texte)
        self.assertIn("published: 2026-10-01", texte)
        self.assertEqual(texte.count("# Un"), 1)   # le titre répété en tête du corps est retiré
        partiel = veille.article_markdown("T", "https://blog.test/a", source, "", "2026-10-01", "Corps", False)
        self.assertIn("Extrait seulement", partiel)
        self.assertIn("complete: false", partiel)

    def test_content_links(self):
        html = ("<p><a href='/interne'>a</a> <a href='https://autre.test/p'>b</a> <a href='https://x.com/u'>c</a>"
                " <a href='https://bit.ly/zz'>d</a> <a href='https://blog.test/autre'>e</a> "
                "<a href='mailto:a@b.c'>f</a> <a href='https://autre.test/p?utm_medium=z'>g</a></p>")
        self.assertEqual(veille.content_links("https://blog.test/a", feed_html=html), {"https://autre.test/p"})

    def test_liens_bluesky_linkedin_et_claude(self):
        post = {"record": {"createdAt": "2026-10-01T10:00:00Z", "text": "voir https://blog.test/a?utm_source=x.",
                           "embed": {"external": {"uri": "https://blog.test/a"}},
                           "facets": [{"features": [{"$type": "app.bsky.richtext.facet#link",
                                                     "uri": "https://autre.test/b"}]}]}}
        liens = veille.links_in_bluesky_post(post)
        self.assertEqual(sorted(u for u, _ in liens), ["https://autre.test/b", "https://blog.test/a"])
        self.assertTrue(all(d == "2026-10-01" for _, d in liens))
        self.assertEqual(veille.message_text({"content": [{"type": "text", "text": "A"}], "text": "A"}), "A")
        self.assertEqual(veille.message_text({"text": "seul"}), "seul")


class Sources(Base):
    def test_sources_depuis_une_liste_de_liens(self):
        liste = self.tmp / "liens.txt"
        liste.write_text("https://blog.test/post-1\nhttps://blog.test/post-2?utm_source=x\n"
                         "https://www.youtube.com/watch?v=1\nhttps://bit.ly/abc\nhttps://sans-flux.test/p\n",
                         encoding="utf-8")
        self.routes["https://blog.test/feed"] = rss([{"title": "T", "link": "https://blog.test/post-1"}])
        self.routes["https://bit.ly/abc"] = httpx.Response(302, headers={"location": "https://autre.test/p"})
        self.routes["https://autre.test/p"] = httpx.Response(200, text="<html></html>",
                                                             headers={"content-type": "text/html"})
        sortie = self.lancer(veille.cmd_sources, bluesky=None, linkedin=None, claude_export=None, urls=str(liste))
        self.assertIn("5 liens lus", sortie)
        self.assertIn("Liens de réseaux sociaux ignorés : 1", sortie)
        sources = {s["key"]: s for s in veille.load_sources()}
        self.assertEqual(set(sources), {"blog.test", "autre.test", "sans-flux.test"})
        self.assertTrue(all(s["active"] is False for s in sources.values()))   # c'est vous qui choisissez
        self.assertEqual((sources["blog.test"]["shared"], sources["blog.test"]["feed_ok"]), (2, True))
        self.assertEqual(sources["blog.test"]["feed"], "https://blog.test/feed")
        self.assertFalse(sources["sans-flux.test"]["feed_ok"])

    def test_source_existante_garde_ses_reglages(self):
        self.activer({"key": "blog.test", "name": "Mon nom", "active": True, "feed": "https://blog.test/mon-flux",
                      "include": ["produit"], "shared": 1})
        liste = self.tmp / "liens.txt"
        liste.write_text("https://blog.test/a\nhttps://blog.test/b\nhttps://blog.test/c\n", encoding="utf-8")
        self.lancer(veille.cmd_sources, bluesky=None, linkedin=None, claude_export=None, urls=str(liste))
        source = veille.load_sources()[0]
        self.assertEqual((source["name"], source["active"], source["feed"], source["include"], source["shared"]),
                         ("Mon nom", True, "https://blog.test/mon-flux", ["produit"], 3))
        self.assertEqual(self.requetes, [])   # aucune recherche de flux pour une source déjà connue

    def test_aucun_lien(self):
        with self.assertRaises(SystemExit):
            self.lancer(veille.cmd_sources, bluesky=None, linkedin=None, claude_export=None, urls=None)

    def test_decouverte_du_flux(self):
        with self.faux_client() as http:
            self.routes["https://blog.test/post"] = httpx.Response(
                200, text='<html><head><link rel="alternate" type="application/rss+xml" href="/rss-blog"></head></html>',
                headers={"content-type": "text/html"})
            self.routes["https://blog.test/rss-blog"] = rss([{"title": "T", "link": "https://blog.test/x"}])
            source = veille.source_of("https://blog.test/post")
            self.assertEqual(veille.discover_feed(http, source, ["https://blog.test/post"]),
                             "https://blog.test/rss-blog")
            self.routes.clear()
            self.assertIsNone(veille.discover_feed(http, source, ["https://blog.test/post"]))


class Collecte(Base):
    def test_ecriture_des_articles_et_rapport(self):
        self.activer(self.source())
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Premier article", "link": "https://blog.test/un", "date": il_y_a(2), "author": "Auteur Inventé",
             "html": paragraphes(30)},
            {"title": "Deuxième article", "link": "https://blog.test/deux", "date": il_y_a(1), "html": paragraphes(30),
             }])
        sortie = self.collecter()
        self.assertIn("blog.test : 2 nouveaux", sortie)
        fichiers = self.articles()
        self.assertEqual(len(fichiers), 2)
        texte = (self.dir / "watch" / f"{(AUJOURDHUI - dt.timedelta(days=2)).isoformat()}-blog-test-premier-article.md"
                 ).read_text(encoding="utf-8")
        for attendu in ('title: "Premier article · Blog inventé"', 'url: "https://blog.test/un"',
                        'source: "blog.test"', 'author: "Auteur Inventé"', "complete: true", "# Premier article"):
            self.assertIn(attendu, texte)
        self.assertNotIn("Extrait seulement", texte)
        self.assertEqual(self.base().execute("SELECT COUNT(*) FROM articles").fetchone()[0], 2)
        rapport = (self.dir / "_rapport_collecte.txt").read_text(encoding="utf-8")
        self.assertIn("2 nouveaux articles · 0 sources en erreur", rapport)
        self.assertEqual(self.requetes, ["https://blog.test/feed"])   # texte complet dans le flux : pas de page

    def test_deduplication(self):
        self.activer(self.source())
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Article", "link": "https://blog.test/un", "date": il_y_a(2), "html": paragraphes(30)}])
        self.collecter()
        # second passage : même article, lien avec paramètre de suivi, plus un nouveau
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Article", "link": "https://blog.test/un?utm_source=rss", "date": il_y_a(2),
             "html": paragraphes(30)},
            {"title": "Autre", "link": "https://blog.test/deux", "date": il_y_a(1), "html": paragraphes(30)}])
        sortie = self.collecter()
        self.assertIn("blog.test : 1 nouveaux", sortie)
        self.assertEqual(len(self.articles()), 2)
        self.assertEqual(self.collecter().count("1 nouveaux"), 0)   # troisième passage : plus rien
        self.assertEqual(len(self.articles()), 2)

    def test_meme_titre_meme_jour_ne_s_ecrase_pas(self):
        self.activer(self.source())
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Même titre", "link": "https://blog.test/un", "date": il_y_a(1), "html": paragraphes(30)},
            {"title": "Même titre", "link": "https://blog.test/deux", "date": il_y_a(1), "html": paragraphes(30, "autre")}])
        self.collecter()
        self.assertEqual(len(self.articles()), 2)
        self.assertTrue(any(f.name.endswith("-2.md") for f in self.articles()))

    def test_meme_article_revenu_sous_une_autre_url_n_est_pas_duplique(self):
        self.activer(self.source())
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Article", "link": "https://blog.test/un", "date": il_y_a(3), "html": paragraphes(30)}])
        self.collecter()
        with self.base() as db:   # collecté un jour précédent
            db.execute("UPDATE articles SET collected = '2020-01-01T00:00:00'")
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Article", "link": "https://autre-hote.test/blog/un", "date": il_y_a(3), "html": paragraphes(30)}])
        sortie = self.collecter()
        self.assertIn("blog.test : 0 nouveaux", sortie)
        self.assertEqual(len(self.articles()), 1)
        self.assertFalse(any(f.name.endswith("-2.md") for f in self.articles()))
        # un titre identique à une autre date de publication reste un autre article
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Article", "link": "https://blog.test/trois", "date": il_y_a(1), "html": paragraphes(30)}])
        self.assertIn("blog.test : 1 nouveaux", self.collecter())

    def test_anciens_articles_filtres_et_lien_absent(self):
        self.activer(self.source())
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Ancien", "link": "https://blog.test/vieux", "date": il_y_a(90), "html": paragraphes(30)},
            {"title": "Sans lien", "date": il_y_a(1), "html": paragraphes(30)},
            {"title": "Récent", "link": "https://blog.test/recent", "date": il_y_a(1), "html": paragraphes(30)}])
        self.collecter(jours=30)
        self.assertEqual(len(self.articles()), 1)
        self.assertIn("recent", self.articles()[0].name)

    def test_mots_cles_include_exclude(self):
        self.activer(self.source(include=["produit"], exclude=["promo"]))
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Produit et flux", "link": "https://blog.test/a", "date": il_y_a(1), "html": paragraphes(30)},
            {"title": "Autre sujet", "link": "https://blog.test/b", "date": il_y_a(1), "html": paragraphes(30)},
            {"title": "Produit promo", "link": "https://blog.test/c", "date": il_y_a(1), "html": paragraphes(30)},
            {"title": "Divers", "tag": "Produit", "link": "https://blog.test/d", "date": il_y_a(1),
             "html": paragraphes(30)}])
        self.collecter()
        self.assertEqual(sorted(a.name.split("-blog-test-")[1] for a in self.articles()),
                         ["divers.md", "produit-et-flux.md"])

    def test_extrait_complete_par_la_page(self):
        self.activer(self.source())
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Extrait", "link": "https://blog.test/un", "date": il_y_a(1), "html": "<p>Court.</p>"}])
        self.routes["https://blog.test/un"] = httpx.Response(
            200, content=page(paragraphes(20), "<p>Voir <a href='https://cite.test/p'>cité</a> pour plus de détails.</p>"),
            headers={"content-type": "text/html"})
        sortie = self.collecter()
        self.assertIn("blog.test : 1 nouveaux", sortie)
        self.assertNotIn("extraits seulement", sortie)
        self.assertIn("complete: true", self.articles()[0].read_text(encoding="utf-8"))
        liens = self.base().execute("SELECT target_url FROM links").fetchall()
        self.assertEqual(liens, [("https://cite.test/p",)])   # liens du corps, pas ceux du menu

    def test_extrait_seulement_quand_la_page_est_inaccessible(self):
        self.activer(self.source())
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Paywall", "link": "https://blog.test/un", "date": il_y_a(1), "html": "<p>Court.</p>"}])
        sortie = self.collecter()
        self.assertIn("blog.test : 1 nouveaux dont 1 extraits seulement", sortie)
        texte = self.articles()[0].read_text(encoding="utf-8")
        self.assertIn("complete: false", texte)
        self.assertIn("Extrait seulement", texte)
        self.assertEqual(self.base().execute("SELECT complete FROM articles").fetchone()[0], 0)

    def test_source_en_erreur_ne_bloque_pas_les_autres(self):
        self.activer(self.source("panne.test"), self.source("blog.test"))
        self.routes["https://panne.test/feed"] = httpx.Response(500, text="oups")
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Article", "link": "https://blog.test/un", "date": il_y_a(1), "html": paragraphes(30)}])
        sortie = self.collecter()
        self.assertIn("panne.test : ERREUR", sortie)
        self.assertIn("blog.test : 1 nouveaux", sortie)
        self.assertEqual(len(self.articles()), 1)
        erreurs = dict(self.base().execute("SELECT source, error FROM runs").fetchall())
        self.assertIn("500", erreurs["panne.test"])
        self.assertIsNone(erreurs["blog.test"])
        self.assertIn("1 sources en erreur", (self.dir / "_rapport_collecte.txt").read_text(encoding="utf-8"))
        # la source répare son flux : l'erreur est effacée au passage suivant
        self.routes["https://panne.test/feed"] = rss([
            {"title": "Réparé", "link": "https://panne.test/un", "date": il_y_a(1), "html": paragraphes(30)}])
        self.collecter()
        self.assertIsNone(dict(self.base().execute("SELECT source, error FROM runs").fetchall())["panne.test"])

    def test_flux_mal_forme(self):
        self.activer(self.source("texte.test"), self.source("vide.test"), self.source("tronque.test"),
                     self.source("injoignable.test"))
        self.routes["https://texte.test/feed"] = httpx.Response(200, text="Ceci n'est pas du XML du tout.")
        self.routes["https://vide.test/feed"] = rss([])
        valide = rss([{"title": "Reçu", "link": "https://tronque.test/un", "date": il_y_a(1), "html": paragraphes(30)},
                      {"title": "Perdu", "link": "https://tronque.test/deux", "date": il_y_a(1),
                       "html": paragraphes(30)}])
        self.routes["https://tronque.test/feed"] = valide[:valide.index(b"<item>", valide.index(b"</item>"))]  # coupé
        self.routes["https://injoignable.test/feed"] = lambda request: (_ for _ in ()).throw(
            httpx.ConnectError("réseau coupé"))
        sortie = self.collecter()
        self.assertIn("texte.test : ERREUR flux illisible", sortie)
        self.assertIn("vide.test : 0 nouveaux", sortie)             # un flux vide est valide, pas une erreur
        self.assertIn("tronque.test : 1 nouveaux", sortie)          # des entrées lisibles suffisent
        self.assertIn("injoignable.test : ERREUR", sortie)
        self.assertIn("2 sources en erreur", (self.dir / "_rapport_collecte.txt").read_text(encoding="utf-8"))

    def test_page_html_a_la_place_du_flux_est_une_erreur(self):
        """Une page HTML servie à la place du flux (refonte du site) est une erreur de la source, visible dans la
        sortie, le rapport et la table `runs` ; la dernière réussite n'avance pas."""
        self.activer(self.source("html.test"))
        self.routes["https://html.test/feed"] = httpx.Response(
            200, text="<html><body>pas un flux</body></html>", headers={"content-type": "text/html; charset=utf-8"})
        sortie = self.collecter()
        self.assertIn("html.test : ERREUR la réponse n'est pas un flux RSS ou Atom (text/html", sortie)
        self.assertIn("1 sources en erreur", (self.dir / "_rapport_collecte.txt").read_text(encoding="utf-8"))
        derniere, erreur = self.base().execute("SELECT last_ok, error FROM runs WHERE source = 'html.test'").fetchone()
        self.assertIsNone(derniere)
        self.assertIn("pas un flux", erreur)

    def test_redirection_vers_l_accueil_est_une_erreur(self):
        self.activer(self.source("accueil.test"))
        self.routes["https://accueil.test/feed"] = httpx.Response(302, headers={"location": "https://accueil.test/"})
        self.routes["https://accueil.test/"] = httpx.Response(
            200, text="<html><body>Accueil du site</body></html>", headers={"content-type": "text/html"})
        sortie = self.collecter()
        self.assertIn("accueil.test : ERREUR la réponse n'est pas un flux RSS ou Atom (text/html, https://accueil.test/)",
                      sortie)

    def test_flux_vide_valide_reste_un_succes(self):
        self.activer(self.source("vide.test"))
        self.routes["https://vide.test/feed"] = rss([])
        self.assertIn("vide.test : 0 nouveaux", self.collecter())
        self.assertIsNotNone(self.base().execute("SELECT last_ok FROM runs WHERE source = 'vide.test'").fetchone()[0])

    def test_aucune_source_active(self):
        with self.assertRaises(SystemExit):
            self.collecter()
        self.activer(self.source(active=False), {"key": "x.test", "name": "x", "active": True, "feed": None})
        with self.assertRaises(SystemExit):
            self.collecter()

    def test_collection_personnelle_rangee_a_part(self):
        self.activer(self.source("medium.com/@moi", collection=OWN))
        self.routes["https://medium.com/@moi/feed"] = rss([
            {"title": "Mon article", "link": "https://medium.com/@moi/mon-article-abc123", "date": il_y_a(1),
             "html": paragraphes(30)}])
        self.collecter()
        self.assertEqual(len(self.articles(OWN)), 1)
        self.assertEqual(self.articles(), [])


class AutresCommandes(Base):
    def collecte_deux_sources(self):
        self.activer(self.source("blog.test"), self.source("medium.com/@moi", name="Moi", collection=OWN))
        self.routes["https://blog.test/feed"] = rss([
            {"title": "À lire", "link": "https://blog.test/un", "date": il_y_a(1), "html": paragraphes(30)}])
        self.routes["https://medium.com/@moi/feed"] = rss([
            {"title": "Le mien", "link": "https://medium.com/@moi/le-mien-abc123", "date": il_y_a(1),
             "html": paragraphes(30)}])
        self.collecter()

    def test_digest_exclut_vos_articles_et_respecte_la_periode(self):
        self.collecte_deux_sources()
        sortie = self.lancer(veille.cmd_digest, days=7)
        self.assertIn("1 articles", sortie)
        texte = (self.dir / "_to-read.md").read_text(encoding="utf-8")
        self.assertIn("[À lire](https://blog.test/un)", texte)
        self.assertNotIn("Le mien", texte)
        # un article collecté il y a longtemps sort de la période
        with self.base() as db:
            db.execute("UPDATE articles SET collected = '2020-01-01T00:00:00'")
        self.lancer(veille.cmd_digest, days=7)
        self.assertIn("0 articles", (self.dir / "_to-read.md").read_text(encoding="utf-8").splitlines()[2])

    def test_liens_reprend_ce_qui_etait_inaccessible(self):
        self.activer(self.source())
        self.routes["https://blog.test/feed"] = rss([
            {"title": "Un", "link": "https://blog.test/un", "date": il_y_a(1), "html": paragraphes(30)},
            {"title": "Deux", "link": "https://blog.test/deux", "date": il_y_a(1), "html": paragraphes(30, "autre")}])
        self.collecter()
        with self.base() as db:   # comme avant que la collecte garde les liens
            db.execute("DELETE FROM links_done")
            db.execute("DELETE FROM links")
        self.routes["https://blog.test/un"] = httpx.Response(
            200, content=page(paragraphes(20), "<p>Voir <a href='https://cite.test/p'>cité</a> pour plus de détails.</p>"),
            headers={"content-type": "text/html"})
        sortie = self.lancer(veille.cmd_links)
        self.assertIn("2 articles dont les liens", sortie)
        self.assertIn("1 pages inaccessibles", sortie)
        self.assertEqual(self.lancer(veille.cmd_links).count("page inaccessible"), 1)   # « Deux » reste à reprendre
        self.assertEqual(self.base().execute("SELECT COUNT(*) FROM links_done").fetchone()[0], 1)

    def test_import_medium(self):
        archive = self.tmp / "medium.zip"
        long = "".join(f"<p>Paragraphe {i} de mon article inventé sur le flux et la discovery, assez long.</p>"
                       for i in range(20))
        post = (f"<html><head><title>Mon article</title></head><body><article><section data-field='body'>"
                f"<h3>Mon article</h3>{long}</section><footer><time class='dt-published' "
                f"datetime='2025-03-04T10:00:00'></time><a class='p-canonical' "
                f"href='https://medium.com/@moi/mon-article-abc123'></a></footer></article></body></html>")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("posts/2025-03-04_Mon-article-abc123.html", post)
            z.writestr("posts/draft_Brouillon-xyz.html", post)
            z.writestr("posts/2025-03-05_Reponse-def456.html",
                       "<html><body><section data-field='body'><p>Réponse courte.</p></section></body></html>")
        options = dict(export=str(archive), source="medium.com/@moi", collection=OWN, author="Un auteur",
                       min_chars=800)
        sortie = self.lancer(veille.cmd_import_medium, **options)
        self.assertIn("importés : 1 · brouillons ignorés : 1 · trop courts (réponses) : 1 · déjà présents : 0", sortie)
        fichier = self.articles(OWN)[0]
        self.assertTrue(fichier.name.startswith("2025-03-04-medium-com-moi-mon-article"))
        texte = fichier.read_text(encoding="utf-8")
        self.assertIn('url: "https://medium.com/@moi/mon-article-abc123"', texte)
        self.assertEqual(texte.count("# Mon article"), 1)
        self.assertIn("déjà présents : 1", self.lancer(veille.cmd_import_medium, **options))   # idempotent
        self.assertEqual(len(self.articles(OWN)), 1)
        self.assertEqual(self.requetes, [])


class ChampNote(Base):
    """`note:` (texte libre) : la raison d'une désactivation survit aux réécritures complètes de sources.yaml."""

    RACINE = Path(__file__).resolve().parents[2]

    def test_aller_retour_conserve_note(self):
        self.activer({**self.source("blog.test"), "active": False, "note": "désactivée le 2026-10-08 (hors sujet)"},
                     self.source("autre.test"))
        sources = veille.load_sources()          # chargement strict
        self.assertEqual(sources[0]["note"], "désactivée le 2026-10-08 (hors sujet)")
        veille.save_sources(sources)
        self.assertEqual(veille.load_sources(), sources)
        self.assertIn("note", veille.SOURCES_HEADER)

    def test_note_survit_a_cmd_sources_et_a_suggestions(self):
        self.activer({**self.source("blog.test"), "active": False, "note": "raison"})
        liste = self.tmp / "liens.txt"
        liste.write_text("https://blog.test/p1\nhttps://nouveau.test/p2\n", encoding="utf-8")
        self.routes["https://nouveau.test/feed"] = rss([])
        self.lancer(veille.cmd_sources, bluesky=None, linkedin=None, claude_export=None, urls=str(liste))
        self.assertEqual({s["key"]: s.get("note") for s in veille.load_sources()}["blog.test"], "raison")


class CoucheLocale(Base):
    """`sources.local.yaml` (à côté du fichier suivi, jamais réécrit) : sources personnelles fusionnées à la lecture."""

    SUFFIXE = " ; corriger le fichier ou le retirer (les sources suivies seront alors lues seules)."

    def local(self, texte: str) -> Path:
        chemin = veille.SOURCES_FILE.with_name("sources.local.yaml")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def erreur(self, texte: str, brut: bytes | None = None) -> str:
        chemin = self.local(texte)
        if brut is not None:
            chemin.write_bytes(brut)
        with self.assertRaises(SystemExit) as ctx:
            veille.load_sources()
        self.assertIsInstance(ctx.exception.code, str)   # message sur l'erreur standard, code de sortie 1
        return str(ctx.exception)

    def test_fichier_local_absent(self):
        self.activer(self.source("a.test"))
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            sources = veille.load_sources()
        self.assertEqual([s["key"] for s in sources], ["a.test"])
        self.assertEqual(sortie.getvalue(), "")

    def test_fichier_local_vide(self):
        self.activer(self.source("a.test"))
        self.local("")
        self.assertEqual([s["key"] for s in veille.load_sources()], ["a.test"])

    def test_cle_locale_ajoutee_apres_les_suivies(self):
        self.activer(self.source("a.test"), self.source("b.test"))
        self.local(yaml.safe_dump({"sources": [self.source("moi.test", collection=OWN)]}))
        self.assertEqual([s["key"] for s in veille.load_sources()], ["a.test", "b.test", "moi.test"])

    def test_entree_locale_remplace_a_sa_place(self):
        self.activer(self.source("a.test"), self.source("b.test"), self.source("c.test"))
        self.local(yaml.safe_dump({"sources": [self.source("b.test", name="Local", collection=OWN)]}))
        sources = veille.load_sources()
        self.assertEqual([s["key"] for s in sources], ["a.test", "b.test", "c.test"])
        self.assertEqual(sources[1]["name"], "Local")

    def test_save_sources_n_ecrit_pas_le_local(self):
        self.activer(self.source("a.test"), self.source("b.test", name="Suivi"))
        chemin = self.local(yaml.safe_dump({"sources": [
            self.source("b.test", name="Local"), self.source("moi.test", collection=OWN)]}))
        avant = chemin.read_text(encoding="utf-8")
        veille.save_sources(veille.load_sources())
        self.assertEqual(chemin.read_text(encoding="utf-8"), avant)
        suivi = yaml.safe_load(veille.SOURCES_FILE.read_text(encoding="utf-8"))["sources"]
        self.assertEqual([s["key"] for s in suivi], ["a.test", "b.test"])
        self.assertEqual(suivi[1]["name"], "Suivi")

    def test_en_tete_mentionne_le_fichier_local(self):
        self.assertIn("sources.local.yaml", veille.SOURCES_HEADER)

    def test_erreur_yaml_avec_ligne(self):
        message = self.erreur("sources: [a\n  - b: : :\n")
        self.assertRegex(message, r"^sources\.local\.yaml : fichier illisible \(L\d+\)" + __import__("re").escape(self.SUFFIXE) + "$")

    def test_erreur_utf8(self):
        message = self.erreur("", brut=b"sources: \xff\xfe\n")
        self.assertEqual(message, "sources.local.yaml : fichier illisible" + self.SUFFIXE)

    def test_erreur_sources_pas_une_liste(self):
        attendu = "sources.local.yaml : « sources » doit être une liste d'entrées" + self.SUFFIXE
        self.assertEqual(self.erreur("sources: 3\n"), attendu)
        self.assertEqual(self.erreur("- a\n- b\n"), attendu)

    def test_erreur_entree_sans_key(self):
        message = self.erreur(yaml.safe_dump({"sources": [self.source("a.test"), {"name": "x"}]}))
        self.assertEqual(message, "sources.local.yaml : entrée 2 sans « key »" + self.SUFFIXE)

    def test_erreur_meme_key_deux_fois(self):
        message = self.erreur(yaml.safe_dump({"sources": [self.source("a.test"), self.source("b.test"),
                                                           self.source("a.test")]}))
        self.assertEqual(message, "sources.local.yaml : entrées 1 et 3 : même « key » ; garder une seule des deux entrées.")

    def test_erreur_cle_ecrite_deux_fois_dans_un_bloc(self):
        message = self.erreur("sources:\n  - key: a.test\n    name: x\n    name: y\n")
        self.assertIn("sources.local.yaml", message)

    def test_collecte_d_une_source_locale_dans_le_dossier_personnel(self):
        self.activer(self.source("blog.test"))
        self.local(yaml.safe_dump({"sources": [self.source("medium.com/@moi", collection=OWN)]}))
        self.routes["https://medium.com/@moi/feed"] = rss([
            {"title": "Mon article", "link": "https://medium.com/@moi/mon-article-abc123", "date": il_y_a(1),
             "html": paragraphes(30)}])
        self.routes["https://blog.test/feed"] = rss([])
        self.collecter()
        self.assertEqual(len(self.articles(OWN)), 1)
        self.assertEqual(self.articles(), [])

    def test_import_medium_sans_collection_va_dans_la_collection_personnelle(self):
        archive = self.tmp / "medium.zip"
        long = "".join(f"<p>Paragraphe {i} de mon article inventé sur le flux et la discovery, assez long.</p>"
                       for i in range(20))
        post = (f"<html><head><title>Mon article</title></head><body><article><section data-field='body'>"
                f"<h3>Mon article</h3>{long}</section><footer><time class='dt-published' "
                f"datetime='2025-03-04T10:00:00'></time><a class='p-canonical' "
                f"href='https://medium.com/@moi/mon-article-abc123'></a></footer></article></body></html>")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("posts/2025-03-04_Mon-article-abc123.html", post)
        with mock.patch.object(veille, "cmd_import_medium") as commande:
            veille.main(["import-medium", str(archive), "--source", "medium.com/@moi", "--author", "Un auteur"])
        self.assertEqual(commande.call_args.args[0].collection, OWN)


class SousCommandes(unittest.TestCase):
    def test_links_remplace_liens_sans_alias(self):
        with mock.patch.object(veille, "cmd_links") as commande:
            veille.main(["links"])
        commande.assert_called_once()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            veille.main(["liens"])


if __name__ == "__main__":
    unittest.main()
