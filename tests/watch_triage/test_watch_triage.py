"""
Tests du pré-tri de la veille (tools/watch_triage.py) sur des articles inventés.

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/watch_triage -v

Tout se passe dans un dossier temporaire (réglages, base du tri, état de la veille, articles, archive) :
jamais Watch-Lab, watch/ ni ~/.pmzilla-lab. Aucun accès réseau ni modèle local : les notes sont insérées
directement dans la base du tri, `veille.client` et `veille.discover_feed` sont remplacés.
Couvre : classement et raisons d'écart, calibration, seuils (avec et sans --save), suggestions de
sources, mode observation puis mode filtre (apply, exclude, restore).
"""
import argparse
import contextlib
import csv
import io
import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import watch_triage as tri  # noqa: E402
import watch_lab as veille  # noqa: E402
import watch_config  # noqa: E402
import watch_paths  # noqa: E402
import identifiants_personnels  # noqa: E402
import flux_config  # noqa: E402

CRITERES = list(tri.CRITERIA)  # these, etaye, original, sources, non_promo


def vecteur(angle: float) -> np.ndarray:
    return np.array([math.cos(angle), math.sin(angle)], dtype=np.float32)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.veille_dir = self.tmp / "Watch-Lab"
        self.articles = self.veille_dir / "watch"
        self.articles.mkdir(parents=True)
        self.archive = self.tmp / "Watch-Excluded" / "watch"
        self.client = mock.MagicMock(name="client")
        self.discover = mock.MagicMock(name="discover_feed", return_value=None)
        for patch in (
            mock.patch.object(tri, "CONFIG_FILE", self.tmp / "watch" / "tri.yaml"),
            mock.patch.object(tri, "TRI_DB", self.tmp / "data" / "tri.sqlite"),
            mock.patch.object(tri, "ARCHIVE_DIR", self.archive),
            mock.patch.object(tri, "CALIBRATION_FILE", self.veille_dir / "_calibration.csv"),
            mock.patch.object(veille, "WATCH_DIR", self.veille_dir),
            mock.patch.object(veille, "ARTICLES_DIR", self.articles),
            mock.patch.object(veille, "SOURCES_FILE", self.tmp / "watch" / "sources.yaml"),
            mock.patch.object(veille, "STATE_DB", self.tmp / "data" / "veille.sqlite"),
            mock.patch.object(veille, "client", self.client),
            mock.patch.object(veille, "discover_feed", self.discover),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.sortie = io.StringIO()
        self.connection = tri.db()
        self.addCleanup(self.connection.close)
        self.connection.execute("INSERT INTO refs VALUES ('r1', 'ref', 'test', ?)", (tri.to_blob(vecteur(0)),))
        self.connection.commit()
        self.compteur = 0

    # -- aides -------------------------------------------------------------

    def lancer(self, commande, **options) -> str:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            commande(argparse.Namespace(**options))
        return sortie.getvalue()

    def ajouter(self, nom, substance, *, titre=None, source="source-a.test", url=None, in_themes=1, promo=0,
                compilation=0, justifs=None, ecrire=True, collecte="2026-10-02"):
        """Insère un article noté ; l'angle croît avec le compteur, donc la pertinence décroît."""
        self.compteur += 1
        criteres = None if substance is None else {k: i < substance for i, k in enumerate(CRITERES)}
        self.connection.execute(
            "INSERT INTO scores (file, url, title, source, published, collected, complete, vector, criteria, "
            "substance, resume, pourquoi, model, scored_at, location, justifications, compilation, in_themes, promo) "
            "VALUES (?, ?, ?, ?, '2026-10-01', ?, 1, ?, ?, ?, 'résumé', 'pourquoi', 'm', 'now', "
            "'watch', ?, ?, ?, ?)",
            (nom, url or f"https://{source}/{nom}", titre or f"Titre {nom}", source, collecte,
             tri.to_blob(vecteur(0.05 * self.compteur)), json.dumps(criteres) if criteres else None, substance,
             json.dumps(justifs) if justifs else None, compilation, in_themes, promo))
        self.connection.commit()
        if ecrire:
            (self.articles / nom).write_text(f"---\ntitle: Titre {nom}\n---\n\ntexte inventé\n", encoding="utf-8")

    def ligne(self, nom):
        return next(r for r in tri.ranked(self.connection) if r["file"] == nom)


class Classement(Base):
    def test_reglages_crees_au_premier_lancement_et_commentaires_conserves(self):
        self.assertFalse(tri.CONFIG_FILE.exists())
        with contextlib.redirect_stdout(self.sortie):
            reglages = tri.config()
        self.assertEqual((reglages["mode"], reglages["substance_threshold"]), ("observation", 3))
        tri.set_config("substance_threshold", 4)
        tri.set_config("nouvelle_cle", "x")
        texte = tri.CONFIG_FILE.read_text(encoding="utf-8")
        self.assertEqual(tri.config()["substance_threshold"], 4)
        self.assertIn("# nombre minimal de critères remplis", texte)
        self.assertEqual(tri.config()["nouvelle_cle"], "x")
        self.assertEqual(tri.config()["mode"], "observation")

    def test_pertinence_en_rang_et_raisons(self):
        self.ajouter("a1.md", 5)
        self.ajouter("a2.md", 4, in_themes=0, justifs={"dans_themes": "sujet technique"})
        self.ajouter("a3.md", 4, promo=1)
        self.ajouter("a4.md", 4, compilation=1)
        self.ajouter("a5.md", None)
        self.ajouter("a6.md", 1)
        with contextlib.redirect_stdout(self.sortie):
            lignes = {r["file"]: r for r in tri.ranked(self.connection)}
        self.assertEqual(lignes["a1.md"]["pertinence"], 100)   # le plus proche de la référence
        self.assertEqual(lignes["a6.md"]["pertinence"], 0)
        self.assertEqual(lignes["a1.md"]["reasons"], [])
        self.assertEqual(lignes["a2.md"]["reasons"], ["hors de vos thèmes (sujet technique)"])
        self.assertEqual(lignes["a3.md"]["reasons"], ["contenu promotionnel"])
        self.assertEqual(lignes["a4.md"]["reasons"], ["compilation de lectures"])
        self.assertEqual(lignes["a5.md"]["reasons"], ["extrait seulement"])
        self.assertEqual(lignes["a6.md"]["reasons"], [tri.CRITERIA[k][1] for k in CRITERES[1:]])

    def test_le_seuil_de_substance_decide(self):
        self.ajouter("a1.md", 3)
        with contextlib.redirect_stdout(self.sortie):
            self.assertEqual(self.ligne("a1.md")["reasons"], [])
            tri.config()
            tri.set_config("substance_threshold", 4)
            self.assertEqual(self.ligne("a1.md")["reasons"], [tri.CRITERIA[k][1] for k in CRITERES[3:]])

    def test_sans_reference_ou_sans_article(self):
        self.connection.execute("DELETE FROM refs")
        self.connection.commit()
        with self.assertRaises(SystemExit):
            tri.ranked(self.connection)
        self.connection.execute("INSERT INTO refs VALUES ('r', 'r', 't', ?)", (tri.to_blob(vecteur(0)),))
        self.connection.commit()
        with self.assertRaises(SystemExit):
            tri.ranked(self.connection)

    def test_ecart_manuel_et_repechage_l_emportent(self):
        self.ajouter("bon.md", 5)
        self.ajouter("faible.md", 0)
        self.connection.execute("INSERT INTO excluded VALUES ('bon.md', 'x')")
        self.connection.execute("INSERT INTO forced VALUES ('faible.md', 'x')")
        self.connection.commit()
        with contextlib.redirect_stdout(self.sortie):
            self.assertEqual(self.ligne("bon.md")["reasons"], ["écarté à la main"])
            self.assertEqual(self.ligne("faible.md")["reasons"], [])


def jeu_de_calibration(self):
    """Onze articles exploitables (5 bons, 6 faibles) et quatre cas de règles fixes."""
    for nom, substance in [("k1", 5), ("k2", 4), ("k3", 4), ("k4", 3), ("k5", 3),
                           ("w1", 2), ("w2", 2), ("w3", 1), ("w4", 1), ("w5", 0), ("w6", 3)]:
        self.ajouter(f"{nom}.md", substance)
    self.ajouter("c1.md", 4, compilation=1)
    self.ajouter("t1.md", 5, in_themes=0)
    self.ajouter("p1.md", 4, promo=1)
    self.ajouter("x1.md", None)


def remplir_avis(avis: dict) -> None:
    with tri.CALIBRATION_FILE.open(encoding="utf-8-sig", newline="") as handle:
        lecteur = csv.DictReader(handle, delimiter=";")
        champs, lignes = lecteur.fieldnames, list(lecteur)
    for ligne in lignes:
        ligne["avis"] = avis.get(ligne["fichier"][:-3], "")
    with tri.CALIBRATION_FILE.open("w", encoding="utf-8-sig", newline="") as handle:
        ecrivain = csv.DictWriter(handle, fieldnames=champs, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


AVIS = {**{k: "g" for k in ("k1", "k2", "k3", "k4", "k5")}, **{k: "e" for k in ("w1", "w2", "w3", "w4", "w5", "w6")},
        "c1": "g", "p1": "g", "t1": "e"}


class Calibration(Base):
    def setUp(self):
        super().setUp()
        jeu_de_calibration(self)

    def test_csv_exporte(self):
        sortie = self.lancer(tri.cmd_calibration)
        self.assertIn("15 articles", sortie)
        with tri.CALIBRATION_FILE.open(encoding="utf-8-sig", newline="") as handle:
            lignes = {r["fichier"]: r for r in csv.DictReader(handle, delimiter=";")}
        self.assertEqual(len(lignes), 15)
        self.assertEqual(lignes["k1.md"]["filtre"], "garder")
        self.assertEqual(lignes["k4.md"]["filtre"], "garder")
        self.assertEqual(lignes["w1.md"]["filtre"], "écarter")
        self.assertIn("pas de position claire", lignes["w5.md"]["manque"].split(", ")[0])
        self.assertEqual((lignes["c1.md"]["compilation"], lignes["p1.md"]["promotionnel"],
                          lignes["t1.md"]["dans_themes"]), ("oui", "oui", "non"))
        self.assertEqual(lignes["x1.md"]["substance"], "")
        self.assertEqual(lignes["x1.md"]["filtre"], "écarter")
        self.assertTrue(all(r["avis"] == "" for r in lignes.values()))

    def test_seuils_sans_calibration(self):
        with self.assertRaises(SystemExit):
            self.lancer(tri.cmd_thresholds, save=False)

    def test_seuils_trop_peu_d_avis(self):
        self.lancer(tri.cmd_calibration)
        remplir_avis({"k1": "g", "w1": "e"})
        with self.assertRaises(SystemExit) as erreur:
            self.lancer(tri.cmd_thresholds, save=False)
        self.assertIn("2 avis", str(erreur.exception))

    def test_seuils_sans_enregistrer(self):
        self.lancer(tri.cmd_calibration)
        remplir_avis(AVIS)
        with contextlib.redirect_stdout(io.StringIO()):
            tri.config()
            tri.set_config("substance_threshold", 1)
        avant = tri.CONFIG_FILE.read_text(encoding="utf-8")
        sortie = self.lancer(tri.cmd_thresholds, save=False)
        self.assertIn("11 avis · seuil actuel : substance 1/5", sortie)
        self.assertIn("Proposition (substance seule) : substance_threshold: 3 (perd 0 bon(s) article(s), garde 1 article(s) faible(s))",
                      sortie)
        self.assertIn("Pour l'enregistrer", sortie)
        self.assertEqual(tri.CONFIG_FILE.read_text(encoding="utf-8"), avant)   # rien d'écrit
        # tableau des seuils : 0 → 6 faibles gardés, 4 → 2 bons perdus
        self.assertRegex(sortie, r"\n\s+0\s+0\s+6\n")
        self.assertRegex(sortie, r"\n\s+4\s+2\s+0\n")

    def test_seuils_desaccords_signales(self):
        self.lancer(tri.cmd_calibration)
        remplir_avis(AVIS)
        sortie = self.lancer(tri.cmd_thresholds, save=False)
        self.assertIn("2 article(s) que vous voulez garder sont écartés par une règle fixe", sortie)
        self.assertIn("(compilation)", sortie)
        self.assertIn("(promotionnel)", sortie)
        self.assertIn("restore c1.md", sortie)
        # le couple proposé (substance 3, pertinence 30) écarte w6, faible et loin de la référence
        self.assertIn("Proposition (substance et pertinence) : substance_threshold: 3, relevance_threshold: 30 "
                      "(accord 11/11, perd 0 bon(s) article(s), garde 0 article(s) faible(s)).", sortie)
        self.assertNotIn("exclude w6.md", sortie)
        self.assertNotIn("t1.md", sortie)   # hors thèmes écarté et voulu écarté : aucun désaccord

    def test_seuils_avec_enregistrer(self):
        self.lancer(tri.cmd_calibration)
        remplir_avis(AVIS)
        with contextlib.redirect_stdout(io.StringIO()):
            tri.config()
            tri.set_config("substance_threshold", 1)
        sortie = self.lancer(tri.cmd_thresholds, save=True)
        self.assertIn("Enregistré dans", sortie)
        self.assertIn("Le mode reste « observation »", sortie)
        reglages = tri.config()
        self.assertEqual((reglages["substance_threshold"], reglages["relevance_threshold"], reglages["mode"]),
                         (3, 30, "observation"))
        self.assertIn("# nombre minimal de critères remplis", tri.CONFIG_FILE.read_text(encoding="utf-8"))

    def test_seuils_a_egalite_prend_le_moins_strict(self):
        self.lancer(tri.cmd_calibration)
        # tous bons : aucun seuil ne perd de bon avant 3, le moins strict (0) gagne
        remplir_avis({k: "g" for k in ("k1", "k2", "k3", "k4", "k5", "w1", "w2", "w3", "w4", "w5", "w6")})
        sortie = self.lancer(tri.cmd_thresholds, save=False)
        self.assertIn("Proposition (substance seule) : substance_threshold: 0", sortie)


class Filtre(Base):
    def setUp(self):
        super().setUp()
        self.ajouter("bon.md", 5)
        self.ajouter("faible.md", 0)
        self.ajouter("promo.md", 5, promo=1)
        self.ajouter("absent.md", 0, ecrire=False)   # noté mais déjà plus dans la bibliothèque
        with contextlib.redirect_stdout(io.StringIO()):
            tri.config()

    def test_observation_ne_deplace_rien(self):
        sortie = self.lancer(tri.cmd_apply)
        self.assertIn("Mode observation", sortie)
        self.assertEqual(sorted(p.name for p in self.articles.glob("*.md")), ["bon.md", "faible.md", "promo.md"])
        self.assertFalse(self.archive.exists())

    def test_filtre_sort_les_articles_ecartes(self):
        tri.set_config("mode", "filtre")
        sortie = self.lancer(tri.cmd_apply)
        self.assertIn("2 article(s) sorti(s)", sortie)
        self.assertEqual([p.name for p in self.articles.glob("*.md")], ["bon.md"])
        self.assertEqual(sorted(p.name for p in self.archive.glob("*.md")), ["faible.md", "promo.md"])
        lieux = dict(self.connection.execute("SELECT file, location FROM scores").fetchall())
        self.assertEqual((lieux["faible.md"], lieux["bon.md"]), ("excluded", "watch"))

    def test_filtre_deux_fois_ne_deplace_plus(self):
        tri.set_config("mode", "filtre")
        self.lancer(tri.cmd_apply)
        self.assertIn("0 article(s) sorti(s)", self.lancer(tri.cmd_apply))

    def test_ecarter_a_la_main(self):
        tri.set_config("mode", "filtre")
        self.assertIn("sera écarté", self.lancer(tri.cmd_exclude, fichier="/x/y/bon.md"))
        self.lancer(tri.cmd_apply)
        self.assertFalse((self.articles / "bon.md").exists())
        self.assertTrue((self.archive / "bon.md").exists())
        with self.assertRaises(SystemExit):
            self.lancer(tri.cmd_exclude, fichier="inconnu.md")

    def test_repecher_ramene_et_protege(self):
        tri.set_config("mode", "filtre")
        self.lancer(tri.cmd_apply)
        self.assertIn("est dans la bibliothèque", self.lancer(tri.cmd_restore, fichier="faible.md"))
        self.assertTrue((self.articles / "faible.md").exists())
        self.assertFalse((self.archive / "faible.md").exists())
        self.assertEqual(self.connection.execute(
            "SELECT location FROM scores WHERE file = 'faible.md'").fetchone()[0], "watch")
        self.assertIn("0 article(s) sorti(s)", self.lancer(tri.cmd_apply))   # protégé malgré la note 0
        self.assertTrue((self.articles / "faible.md").exists())
        with self.assertRaises(SystemExit):
            self.lancer(tri.cmd_restore, fichier="inconnu.md")

    def test_repecher_annule_un_ecart_manuel(self):
        tri.set_config("mode", "filtre")
        self.lancer(tri.cmd_exclude, fichier="bon.md")
        self.lancer(tri.cmd_restore, fichier="bon.md")
        self.lancer(tri.cmd_apply)
        self.assertTrue((self.articles / "bon.md").exists())


class Suggestions(Base):
    def setUp(self):
        super().setUp()
        self.etat = veille.state()
        self.addCleanup(self.etat.close)

    def citer(self, article, *cibles):
        for cible in cibles:
            self.etat.execute("INSERT OR IGNORE INTO links VALUES (?, ?)", (article, cible))
        self.etat.commit()

    def lancer_suggestions(self, **options):
        defaut = dict(min=2, max=30, reset=False)
        return self.lancer(tri.cmd_suggestions, **{**defaut, **options})

    def sources(self):
        return {s["key"]: s for s in veille.load_sources()}

    def test_source_citee_par_deux_sources_est_proposee_inactive(self):
        self.ajouter("a1.md", 5, source="s1.test", url="https://s1.test/a1")
        self.ajouter("a2.md", 4, source="s2.test", url="https://s2.test/a2")
        self.citer("https://s1.test/a1", "https://blog-a.test/post-1")
        self.citer("https://s2.test/a2", "https://blog-a.test/post-2")
        self.discover.return_value = "https://blog-a.test/feed"
        sortie = self.lancer_suggestions()
        self.assertIn("blog-a.test · cité par 2 articles de 2 source(s) · flux trouvé", sortie)
        proposee = self.sources()["blog-a.test"]
        self.assertFalse(proposee["active"])
        self.assertEqual((proposee["feed"], proposee["feed_ok"], proposee["cited"], proposee["cited_by_sources"]),
                         ("https://blog-a.test/feed", True, 2, 2))
        self.assertEqual(sorted(proposee["examples"]), ["https://blog-a.test/post-1", "https://blog-a.test/post-2"])

    def test_ce_qui_ne_compte_pas(self):
        self.ajouter("a1.md", 5, source="s1.test", url="https://s1.test/a1")
        self.ajouter("a2.md", 5, source="s1.test", url="https://s1.test/a2")   # même source citante
        self.ajouter("a3.md", 5, source="s2.test", url="https://s2.test/a3")
        self.ajouter("a4.md", 5, source="s3.test", url="https://s3.test/a4")
        self.ajouter("faible.md", 0, source="s4.test", url="https://s4.test/f")  # écarté : ne cite pas
        self.ajouter("faible2.md", 0, source="s5.test", url="https://s5.test/f")
        for article in ("a1", "a2"):
            self.citer(f"https://s1.test/{article}", "https://sponsor.test/post")      # une seule source citante
        for numero, article in enumerate(("https://s1.test/a1", "https://s2.test/a3", "https://s3.test/a4")):
            self.citer(article, "https://www.amazon.com/dp/123", "https://exemple.test/", "https://img.test/x.png",
                       "https://medium.com/", f"https://seule-{numero}.test/post")   # chacune citée une fois
        for article in ("https://s4.test/f", "https://s5.test/f"):
            self.citer(article, "https://mauvais.test/p-" + article[-4:])
        self.citer("https://s2.test/a3", "https://deja-suivie.test/p1")
        self.citer("https://s3.test/a4", "https://deja-suivie.test/p2")
        self.citer("https://s1.test/a1", "https://deja-suivie.test/p3")
        veille.save_sources([{"key": "deja-suivie.test", "name": "deja-suivie.test", "active": True}])
        sortie = self.lancer_suggestions()
        self.assertIn("Aucune source citée", sortie)
        self.assertEqual(list(self.sources()), ["deja-suivie.test"])
        self.discover.assert_not_called()

    def test_compilation_suffit_avec_une_seule_source(self):
        self.ajouter("c1.md", 4, source="news.test", url="https://news.test/c1", compilation=1)
        self.ajouter("c2.md", 4, source="news.test", url="https://news.test/c2", compilation=1)
        self.citer("https://news.test/c1", "https://blog-c.test/p1")
        self.citer("https://news.test/c2", "https://blog-c.test/p2")
        sortie = self.lancer_suggestions()
        self.assertIn("blog-c.test", sortie)
        self.assertIn("pas de flux", sortie)
        self.assertFalse(self.sources()["blog-c.test"]["feed_ok"])

    def test_source_deja_proposee_mise_a_jour_et_active_intacte(self):
        self.ajouter("a1.md", 5, source="s1.test", url="https://s1.test/a1")
        self.ajouter("a2.md", 5, source="s2.test", url="https://s2.test/a2")
        self.citer("https://s1.test/a1", "https://blog-a.test/p1")
        self.citer("https://s2.test/a2", "https://blog-a.test/p2")
        veille.save_sources([{"key": "blog-a.test", "name": "blog-a.test", "active": False, "cited": 1,
                              "suggested": "2026-09-01", "feed": "https://blog-a.test/rss", "feed_ok": True}])
        sortie = self.lancer_suggestions()
        self.assertIn("0 nouvelles sources proposées, 1 mises à jour", sortie)
        source = self.sources()["blog-a.test"]
        self.assertEqual((source["cited"], source["feed"], source["suggested"]), (2, "https://blog-a.test/rss", "2026-09-01"))
        self.discover.assert_not_called()

    def test_max_limite_et_ordre(self):
        for i, auteur in enumerate(("s1", "s2", "s3")):
            self.ajouter(f"a{i}.md", 5, source=f"{auteur}.test", url=f"https://{auteur}.test/a")
            self.citer(f"https://{auteur}.test/a", "https://populaire.test/p1", "https://rare.test/p1"
                       if i < 2 else "https://autre.test/p")
        sortie = self.lancer_suggestions(min=1, max=1)
        self.assertIn("1 sources citées", sortie)
        self.assertEqual([k for k in self.sources()], ["populaire.test"])   # citée par 3 sources

    def test_reset_retire_les_suggestions_jamais_activees(self):
        self.ajouter("a1.md", 5)   # base non vide : le chemin normal de `--reset`
        veille.save_sources([
            {"key": "ancienne.test", "name": "ancienne.test", "active": False, "suggested": "2026-08-01"},
            {"key": "suivie.test", "name": "suivie.test", "active": True},
            {"key": "manuelle.test", "name": "manuelle.test", "active": False},   # jamais suggérée : conservée
        ])
        sortie = self.lancer_suggestions(reset=True)   # aucun lien : rien à proposer
        self.assertIn("anciennes suggestions inactives ont été retirées", sortie)
        self.assertEqual(sorted(self.sources()), ["manuelle.test", "suivie.test"])

    def test_reset_sur_une_base_vide_finit_proprement_et_nettoie(self):
        """Aucun article noté : pas d'erreur (ni SystemExit, ni référence exigée), un message clair, et --reset
        retire quand même les suggestions jamais activées."""
        veille.save_sources([
            {"key": "ancienne.test", "name": "ancienne.test", "active": False, "suggested": "2026-08-01"},
            {"key": "autre-ancienne.test", "name": "autre-ancienne.test", "active": False, "suggested": "2026-08-02"},
            {"key": "suivie.test", "name": "suivie.test", "active": True, "suggested": "2026-07-01"},
            {"key": "manuelle.test", "name": "manuelle.test", "active": False},
        ])
        sortie = self.lancer_suggestions(reset=True)                     # lève SystemExit s'il y a une erreur
        self.assertIn("Aucun article noté : il n'y a aucune suggestion à calculer", sortie)
        self.assertIn("watch_triage.py score", sortie)
        self.assertIn("anciennes suggestions inactives ont été retirées de sources.yaml (2)", sortie)
        self.assertEqual(sorted(self.sources()), ["manuelle.test", "suivie.test"])   # active et manuelle conservées
        self.client.assert_not_called()
        self.discover.assert_not_called()

    def test_reset_sur_une_base_vide_sans_suggestion_a_retirer(self):
        veille.save_sources([{"key": "suivie.test", "name": "suivie.test", "active": True}])
        sortie = self.lancer_suggestions(reset=True)
        self.assertIn("Aucune ancienne suggestion inactive à retirer", sortie)
        self.assertEqual(list(self.sources()), ["suivie.test"])

    def test_base_vide_sans_reset_ne_touche_pas_aux_sources_et_n_est_pas_une_erreur(self):
        veille.save_sources([{"key": "ancienne.test", "name": "ancienne.test", "active": False,
                              "suggested": "2026-08-01"}])
        sortie = self.lancer_suggestions()
        self.assertIn("Aucun article noté", sortie)
        self.assertNotIn("retirées", sortie)
        self.assertEqual(list(self.sources()), ["ancienne.test"])         # sans --reset : rien n'est retiré

    def test_aucun_acces_reseau_hors_decouverte_de_flux(self):
        self.ajouter("a1.md", 5)
        self.lancer_suggestions()
        self.client.assert_not_called()   # pas de résultat : aucun client ouvert

class Reglages(Base):
    """Clés de tri.yaml (7.6) : nouveaux noms ; les anciens noms sont refusés avec le nom actuel."""

    ANCIEN = "mode: filtre\nmodele: m1   # modèle\na_lire: 5\njours: 7\nseuil_substance: 3  # seuil\nthemes:\n  - x\n"
    NOUVEAU = ANCIEN.replace("modele", "model").replace("a_lire", "to_read").replace("jours", "days").replace(
        "seuil_substance", "substance_threshold")

    def charger(self, texte):
        tri.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tri.CONFIG_FILE.write_text(texte, encoding="utf-8")
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur):
            reglages = tri.config()
        return reglages, erreur.getvalue()

    def test_anciens_noms_refuses_avec_le_nom_actuel(self):
        for ancien, nouveau in watch_config.KEYS.items():
            with self.assertRaises(SystemExit) as ctx:
                self.charger(f"mode: filtre\n{ancien}: 3\n")
            self.assertIn(f"« {ancien} » n'existe plus ; utiliser « {nouveau} »", str(ctx.exception))
            self.assertIn("L2", str(ctx.exception))

    def test_nouveaux_noms_charges_sans_avertissement(self):
        reglages, erreur = self.charger(self.NOUVEAU)
        self.assertEqual((reglages["model"], reglages["substance_threshold"]), ("m1", 3))
        self.assertEqual(erreur, "")

    def test_ancien_et_nouveau_nom_du_meme_reglage_refuses(self):
        with self.assertRaises(SystemExit) as ctx:
            self.charger(self.ANCIEN + "substance_threshold: 4\n")
        self.assertIn("n'existe plus", str(ctx.exception))

    def test_reglages_par_defaut_en_nouveaux_noms(self):
        reglages, erreur = self.charger(tri.DEFAULT_CONFIG)
        self.assertEqual(erreur, "")
        self.assertEqual(set(reglages) & set(watch_config.KEYS), set())
        self.assertIn("substance_threshold", reglages)

    def test_set_config_en_nouveaux_noms_et_ajout_si_absent(self):
        self.charger(self.NOUVEAU.replace("substance_threshold: 3  # seuil\n", ""))
        tri.set_config("substance_threshold", 2)
        self.assertEqual(self.charger(tri.CONFIG_FILE.read_text(encoding="utf-8"))[0]["substance_threshold"], 2)

    def test_migrate_text_garde_commentaires_et_est_idempotent(self):
        nouveau, changements = watch_config.migrate_text(self.ANCIEN)
        self.assertEqual(nouveau, self.NOUVEAU)
        self.assertEqual(len(changements), 4)
        self.assertEqual(watch_config.migrate_text(nouveau), (nouveau, []))

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        for ancien, nouveau in tri.OLD_OPTIONS.items():
            for argument in (ancien, f"{ancien}=3"):
                erreur = io.StringIO()
                with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as ctx:
                    flux_config.refuse_old_options(["x", argument], tri.OLD_OPTIONS)
                self.assertNotEqual(ctx.exception.code, 0)
                self.assertIn(f"l'option « {ancien} » n'existe plus ; utiliser « {nouveau} »", erreur.getvalue())
        self.assertEqual(flux_config.refuse_old_options(["x", "--save", "--", "--jours"], tri.OLD_OPTIONS),
                         ["x", "--save", "--", "--jours"])

    def test_main_accepte_les_nouveaux_noms_et_refuse_les_anciens(self):
        with mock.patch.object(tri, "cmd_thresholds") as commande:
            tri.main(["thresholds", "--save"])
        self.assertTrue(commande.call_args[0][0].save)
        with mock.patch.object(tri, "cmd_week") as commande:
            tri.main(["week", "--days", "3", "--per-run"])
        self.assertEqual((commande.call_args[0][0].days, commande.call_args[0][0].per_run), (3, True))
        with mock.patch.object(tri, "cmd_references") as commande:
            tri.main(["references", "--claude-export", "x.zip", "--without-own"])
        self.assertTrue(commande.call_args[0][0].without_own)
        for argv in (["thresholds", "--enregistrer"], ["week", "--jours", "3"], ["week", "--par-collecte"]):
            with mock.patch.object(tri, "cmd_thresholds") as t, mock.patch.object(tri, "cmd_week") as w, \
                    contextlib.redirect_stderr(io.StringIO()) as erreur, self.assertRaises(SystemExit) as ctx:
                tri.main(argv)
            self.assertNotEqual(ctx.exception.code, 0)
            self.assertIn("n'existe plus", erreur.getvalue())
            t.assert_not_called()
            w.assert_not_called()

    def test_anciennes_sous_commandes_refusees_sans_alias(self):
        for ancien in ("appliquer", "ecarter", "partages", "repecher", "semaine", "seuils"):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                tri.main([ancien])

    def test_aucun_identifiant_personnel_dans_les_options_ni_dans_l_aide(self):
        racine = Path(__file__).resolve().parents[2]
        aide = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(aide):
            tri.main(["references", "--help"])
        options = " ".join(tri.OLD_OPTIONS.values()).lower()
        for identifiant in identifiants_personnels.identifiants(racine):
            self.assertFalse(identifiant in aide.getvalue().lower(),
                             "l'aide de references contient un identifiant personnel")
            self.assertFalse(identifiant in options, "un nom d'option contient un identifiant personnel")


class CollectionPersonnelle(Base):
    def test_dossier_de_la_collection_personnelle(self):
        self.assertEqual(tri.OWN_DIR.name, watch_paths.OWN_COLLECTION)

    def test_references_etiquette_et_conserve_les_partages(self):
        own = self.tmp / "own"
        own.mkdir()
        (own / "a.md").write_text('---\ntitle: "Mon article"\nurl: https://x.test/a\n---\n\nCorps de l\'article.\n',
                                  encoding="utf-8")
        self.connection.execute("INSERT INTO refs VALUES ('p', 'p', 'partage', ?)", (tri.to_blob(vecteur(0)),))
        self.connection.execute("INSERT INTO refs VALUES ('o', 'o', 'ancienne-etiquette', ?)", (tri.to_blob(vecteur(0)),))
        self.connection.execute("INSERT INTO refs VALUES ('s', 's', 'signalpm', ?)", (tri.to_blob(vecteur(0)),))
        self.connection.commit()
        args = argparse.Namespace(claude_export=["x.zip"], without_own=False)
        sortie = io.StringIO()
        with mock.patch.object(tri, "OWN_DIR", own), \
                mock.patch.object(tri, "signalpm_references", return_value=[]), \
                mock.patch.object(tri.library, "embed", side_effect=lambda textes: [vecteur(0) for _ in textes]), \
                contextlib.redirect_stdout(sortie):
            tri.cmd_references(args)
        origines = dict(self.connection.execute("SELECT url, origin FROM refs").fetchall())
        self.assertEqual(origines.get("https://x.test/a"), watch_paths.OWN_COLLECTION)
        self.assertEqual(origines.get("p"), "partage")
        self.assertNotIn("o", origines)
        self.assertNotIn("s", origines)
        self.assertIn(f"1 articles de la collection {watch_paths.OWN_COLLECTION}", sortie.getvalue())


def verifier_sources(sources) -> list[str]:
    """Problèmes de structure d'une liste de sources : clé unique, `active` booléen, note non vide si elle est présente sur une source inactive."""
    problemes, vues = [], set()
    for rang, s in enumerate(sources, start=1):
        cle = s.get("key")
        if not cle or cle in vues:
            problemes.append(f"entrée {rang} : clé absente ou en double")
        vues.add(cle)
        if not isinstance(s.get("active"), bool):
            problemes.append(f"entrée {rang} : `active` n'est pas un booléen")
        elif not s["active"] and "note" in s and not str(s["note"] or "").strip():
            problemes.append(f"entrée {rang} : source désactivée avec une note vide")
    return problemes


def verifier_reglages(reglages: dict) -> list[str]:
    """Problèmes des réglages suivis hors mode et seuil de substance ; aucun message ne contient de valeur."""
    problemes = []
    if reglages.get("language", "fr") not in ("fr", "en"):
        problemes.append("language doit valoir fr ou en")
    pertinence = reglages.get("relevance_threshold")
    if pertinence is not None and (not isinstance(pertinence, int) or isinstance(pertinence, bool)
                                   or not 0 <= pertinence <= 100):
        problemes.append("relevance_threshold doit être un entier de 0 à 100")
    if str(reglages.get("bluesky") or "").strip():
        problemes.append("bluesky renseigné dans le fichier suivi : à déplacer dans tri.local.yaml")
    return problemes


class FichiersSuivis(unittest.TestCase):
    """Garde-fou structurel : aucune date, aucun seuil exact, aucun nom de source en dur."""

    RACINE = Path(__file__).resolve().parents[2]

    def dossier(self):
        return self.RACINE / "watch" if (self.RACINE / "watch").is_dir() else self.RACINE / "veille"

    def test_reglages_valides(self):
        """Le mode filtre de l'auteur est gardé par tests/private_guards (exclu de l'édition, dont le gabarit est en observation)."""
        reglages = watch_config.normalize(yaml.safe_load((self.dossier() / "tri.yaml").read_text(encoding="utf-8")))
        self.assertIn(reglages["mode"], ("observation", "filtre"))
        seuil = reglages["substance_threshold"]
        self.assertIsInstance(seuil, int)
        self.assertNotIsInstance(seuil, bool)
        self.assertTrue(0 <= seuil <= len(tri.CRITERIA))
        self.assertEqual(verifier_reglages(reglages), [])

    def test_garde_refuse_un_identifiant_suivi_sans_l_afficher(self):
        reglages = {"mode": "filtre", "substance_threshold": 3, "bluesky": "compte-invente.test"}
        problemes = verifier_reglages(reglages)
        self.assertEqual(len(problemes), 1)
        self.assertNotIn("compte-invente", problemes[0])
        for mauvais in ({"language": "de"}, {"relevance_threshold": 101}, {"relevance_threshold": True}):
            self.assertEqual(len(verifier_reglages({**reglages, "bluesky": "", **mauvais})), 1, mauvais)
        self.assertEqual(verifier_reglages({**reglages, "bluesky": None, "language": "en", "relevance_threshold": 50}), [])

    def test_couche_locale_ignoree_et_non_suivie(self):
        import subprocess
        local = "watch/tri.local.yaml"
        suivi = subprocess.run(["git", "ls-files", local], cwd=self.RACINE, capture_output=True, text=True)
        self.assertEqual(suivi.stdout.strip(), "")
        ignore = subprocess.run(["git", "check-ignore", "-q", local], cwd=self.RACINE)
        self.assertEqual(ignore.returncode, 0)

    def test_sources_bien_formees(self):
        sources = yaml.safe_load((self.dossier() / "sources.yaml").read_text(encoding="utf-8"))["sources"]
        self.assertEqual(verifier_sources(sources), [])

    def test_garde_refuse_note_vide_et_cle_dupliquee_mais_pas_l_absence_de_note(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "sources.yaml"
            f.write_text("sources:\n- {key: a, active: false}\n- {key: b, active: false, note: ' '}\n"
                         "- {key: c, active: true}\n- {key: c, active: true}\n", encoding="utf-8")
            problemes = verifier_sources(yaml.safe_load(f.read_text(encoding="utf-8"))["sources"])
        self.assertEqual(len(problemes), 2)          # l'entrée 1 (inactive, sans note) est acceptée
        self.assertIn("entrée 2", problemes[0])
        self.assertIn("entrée 4", problemes[1])


if __name__ == "__main__":
    unittest.main()
