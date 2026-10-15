"""
Tests de tools/watch_store.py : un test de contrat passé au faux en mémoire (toujours) et à PostgreSQL (sauté sans base).

    uv run --with "psycopg[binary]" --with numpy python -m unittest discover -s tests/watch_store -v

Le faux (tests/fixtures_watch/fake_store.py) et le vrai magasin doivent rendre les mêmes valeurs pour les mêmes écritures : dates,
instants, booléens, JSON, vecteurs float16, ordre par nom de fichier. La partie PostgreSQL crée une base jetable pmzilla_test_<hex>
(migrée puis supprimée dans tous les cas), jamais les schémas réels. Données inventées.
"""
import contextlib
import datetime as dt
import re
import secrets
import sys
import unittest
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "fixtures_watch"))
sys.path.insert(0, str(RACINE / "tests" / "db"))
import watch_store as ws  # noqa: E402
import fake_store  # noqa: E402
import test_db as base  # noqa: E402
from test_db import db  # noqa: E402


def vecteur(angle: float) -> np.ndarray:
    v = np.zeros(1024, dtype=np.float32)
    v[0], v[1] = np.cos(angle), np.sin(angle)
    return v


def egaux(testcase, a: np.ndarray, b: np.ndarray) -> None:
    testcase.assertEqual(a.dtype, np.float32)
    np.testing.assert_array_equal(a, np.asarray(b, dtype=np.float16).astype(np.float32))


MIDI = dt.datetime(2026, 10, 1, 12, 0, 0).astimezone()


class Contrat:
    """Assertions communes ; la sous-classe fournit `ouvrir(readonly)` -> (WatchStore, TriageStore) et `compter`."""

    def ouvrir(self, readonly=False):
        raise NotImplementedError

    def setUp(self):
        self.watch, self.triage = self.ouvrir()

    def note(self, fichier, **valeurs):
        defaut = dict(file=fichier, url=f"https://a.test/{fichier}", title=f"Titre {fichier}", source="a.test", published="2026-10-01",
                      collected=MIDI, complete=True, embedding=vecteur(0.1), criteria={"these": True, "etaye": False}, substance=1,
                      summary="résumé", why="apport", model="m", scored_at=MIDI, location="watch", justifications={"these": "parce que"},
                      is_compilation=False, in_themes=True, is_promo=False)
        defaut.update(valeurs)
        self.triage.put_score(**defaut)

    # -- collecte -----------------------------------------------------------

    def test_article_aller_retour_et_unicite(self):
        self.watch.add_article("https://a.test/1", "a.test", "T", "f.md", "2026-10-01", True, MIDI)
        self.watch.commit()
        self.assertTrue(self.watch.article_exists("https://a.test/1"))
        self.assertFalse(self.watch.article_exists("https://a.test/2"))
        [article] = self.watch.articles()
        self.assertEqual(article["published"], dt.date(2026, 10, 1))
        self.assertIs(article["complete"], True)
        self.assertIs(article["links_extracted"], False)
        self.assertEqual(article["collected"], MIDI)
        with self.assertRaises(Exception):
            self.watch.add_article("https://a.test/1", "a.test", "autre", "g.md", None, False, MIDI)
        self.watch.rollback()

    def test_date_de_publication_absente(self):
        self.watch.add_article("https://a.test/1", "a.test", "T", "f.md", None, False, MIDI)
        self.assertIsNone(self.watch.articles()[0]["published"])

    def test_liens_marquent_les_liens_releves_et_sont_sans_doublon(self):
        self.watch.add_article("https://a.test/1", "a.test", "T", "f.md", "2026-10-01", True, MIDI)
        self.watch.add_article("https://a.test/2", "a.test", "U", "g.md", "2026-10-02", True, MIDI + dt.timedelta(hours=1))
        self.assertEqual([u for u, _ in self.watch.links_todo()], ["https://a.test/1", "https://a.test/2"])
        self.watch.add_links("https://a.test/1", {"https://c.test/x", "https://c.test/y"})
        self.watch.add_links("https://a.test/1", {"https://c.test/x"})
        self.assertEqual(self.watch.all_links(), [("https://a.test/1", "https://c.test/x"), ("https://a.test/1", "https://c.test/y")])
        self.assertEqual([u for u, _ in self.watch.links_todo()], ["https://a.test/2"])
        self.watch.add_links("https://a.test/2", set())      # aucun lien trouvé : l'article est quand même marqué
        self.assertEqual(self.watch.links_todo(), [])

    def test_passages_des_sources(self):
        self.watch.record_run_error("a.test", MIDI, "flux illisible")
        self.assertEqual(self.watch.source_runs()["a.test"], {"last_try": MIDI, "last_ok": None, "error": "flux illisible"})
        self.watch.record_run_ok("a.test", MIDI + dt.timedelta(days=1))
        self.assertEqual(self.watch.source_runs()["a.test"],
                         {"last_try": MIDI + dt.timedelta(days=1), "last_ok": MIDI + dt.timedelta(days=1), "error": None})
        self.watch.record_run_error("a.test", MIDI + dt.timedelta(days=2), "panne")
        self.assertEqual(self.watch.source_runs()["a.test"]["last_ok"], MIDI + dt.timedelta(days=1))   # le dernier succès reste

    def test_doublon_d_un_jour_precedent(self):
        self.watch.add_article("https://a.test/1", "a.test", "T", "f.md", "2026-10-01", True, MIDI)
        jour = MIDI.date()
        self.assertTrue(self.watch.earlier_duplicate("a.test", "T", dt.date(2026, 10, 1), jour + dt.timedelta(days=1)))
        self.assertFalse(self.watch.earlier_duplicate("a.test", "T", dt.date(2026, 10, 1), jour))          # collecté le jour même
        self.assertFalse(self.watch.earlier_duplicate("a.test", "autre", dt.date(2026, 10, 1), jour + dt.timedelta(days=1)))

    def test_articles_depuis_une_date_par_source_et_publication_decroissante(self):
        self.watch.add_article("https://b.test/1", "b.test", "B1", "b1.md", "2026-10-01", True, MIDI)
        self.watch.add_article("https://a.test/1", "a.test", "A1", "a1.md", "2026-09-30", False, MIDI)
        self.watch.add_article("https://a.test/2", "a.test", "A2", "a2.md", "2026-10-01", True, MIDI)
        self.watch.add_article("https://a.test/0", "a.test", "A0", "a0.md", "2026-09-01", True, MIDI - dt.timedelta(days=30))
        lignes = self.watch.articles_collected_since(MIDI.date())
        self.assertEqual([(l[0], l[1]) for l in lignes], [("a.test", "A2"), ("a.test", "A1"), ("b.test", "B1")])
        self.assertEqual(lignes[1][3:5], (dt.date(2026, 9, 30), False))

    # -- pré-tri ------------------------------------------------------------

    def test_references_remplacees_sauf_les_partages(self):
        self.triage.put_reference("u1", "t1", "signalpm", vecteur(0.0))
        self.triage.put_reference("u2", "t2", "partage", vecteur(0.5))
        self.triage.replace_references([("u3", "t3", "own", vecteur(1.0))])
        vecteurs = self.triage.reference_vectors()
        self.assertEqual(len(vecteurs), 2)
        egaux(self, vecteurs[0], vecteur(0.5))       # u2, par adresse
        egaux(self, vecteurs[1], vecteur(1.0))       # u3

    def test_note_aller_retour_complet(self):
        self.note("a.md")
        [ligne] = self.triage.all_scores()
        self.assertEqual(ligne["published"], dt.date(2026, 10, 1))
        self.assertEqual(ligne["collected"], MIDI)
        self.assertEqual(ligne["criteria"], {"these": True, "etaye": False})
        self.assertEqual(ligne["justifications"], {"these": "parce que"})
        self.assertIs(ligne["complete"], True)
        self.assertIs(ligne["is_compilation"], False)
        self.assertIs(ligne["in_themes"], True)
        self.assertEqual((ligne["summary"], ligne["why"], ligne["location"], ligne["substance"]), ("résumé", "apport", "watch", 1))
        egaux(self, ligne["embedding"], vecteur(0.1))

    def test_note_extrait_seulement_valeurs_vides(self):
        self.note("e.md", criteria=None, substance=None, justifications=None, is_compilation=None, in_themes=None, is_promo=None,
                  complete=False)
        [ligne] = self.triage.all_scores()
        for nom in ("criteria", "substance", "justifications", "is_compilation", "in_themes", "is_promo"):
            self.assertIsNone(ligne[nom], nom)

    def test_note_remplacee_et_ordre_par_nom_de_fichier(self):
        for nom in ("c.md", "a.md", "b.md"):           # écrites dans l'ordre inverse : le tri ne suit pas l'insertion
            self.note(nom)
        self.assertEqual([s["file"] for s in self.triage.all_scores()], ["a.md", "b.md", "c.md"])
        self.note("a.md", substance=5, location="excluded")
        self.triage.put_score(**{**self.triage.all_scores()[0], "location": None})        # une ligne reprise telle quelle
        self.assertEqual(self.triage.all_scores()[0]["substance"], 5)
        self.assertEqual(self.triage.location_of("a.md"), "watch")
        self.assertIsNone(self.triage.location_of("zz.md"))

    def test_fichiers_signales_faibles_et_emplacement(self):
        self.note("a.md", is_compilation=True, substance=0)
        self.note("b.md", is_promo=True, substance=2)
        self.note("c.md", substance=None, criteria=None)
        self.assertEqual(self.triage.score_files(), {"a.md", "b.md", "c.md"})
        self.assertEqual(self.triage.flagged_files("compilation"), {"a.md"})
        self.assertEqual(self.triage.flagged_files("promo"), {"b.md"})
        self.assertEqual(self.triage.weak_files(2), {"a.md", "b.md"})
        self.triage.set_location("a.md", "excluded")
        self.assertEqual(self.triage.location_of("a.md"), "excluded")

    def test_adresses_des_notes(self):
        self.note("a.md", url="https://a.test/a")
        self.note("b.md", url="")
        self.note("c.md", url=None)
        [(fichier, url, vec)] = self.triage.score_urls()
        self.assertEqual((fichier, url), ("a.md", "https://a.test/a"))
        egaux(self, vec, vecteur(0.1))

    def test_exclusion_et_repechage(self):
        self.note("a.md")
        self.triage.exclude("a.md", "2026-10-02")
        self.assertEqual((self.triage.excluded_files(), self.triage.forced_files()), ({"a.md"}, set()))
        self.triage.set_location("a.md", "excluded")
        self.triage.restore("a.md", dt.date(2026, 10, 3))
        self.assertEqual((self.triage.excluded_files(), self.triage.forced_files()), (set(), {"a.md"}))
        self.assertEqual(self.triage.location_of("a.md"), "watch")
        self.triage.exclude("a.md", "2026-10-04")
        self.assertEqual((self.triage.excluded_files(), self.triage.forced_files()), ({"a.md"}, set()))

    def test_partages_et_selections_du_jour(self):
        self.triage.add_share("a.md", "https://a.test/a", "2026-10-01", dt.date(2026, 10, 2))
        self.triage.add_share("b.md", "https://a.test/b", None, "2026-09-01")
        with self.assertRaises(Exception):
            self.triage.add_share("a.md", "x", None, None)
        self.triage.rollback()
        self.assertEqual(self.triage.shared_files(), set())      # l'annulation a repris les deux ajouts
        self.triage.add_share("a.md", "https://a.test/a", "2026-10-01", dt.date(2026, 10, 2))
        self.triage.add_share("b.md", "https://a.test/b", None, "2026-09-01")
        self.assertEqual(self.triage.share_total(), 2)
        self.assertEqual(self.triage.shared_found_since(dt.date(2026, 9, 15)), [("a.md", dt.date(2026, 10, 2))])
        self.triage.add_picks("2026-10-01", ["a.md", "b.md"])
        self.triage.add_picks(dt.date(2026, 10, 1), ["a.md"])      # sans doublon
        self.assertEqual(self.triage.pick_days(), [(dt.date(2026, 10, 1), "a.md"), (dt.date(2026, 10, 1), "b.md")])
        self.assertTrue(self.triage.picked_on_or_before("a.md", dt.date(2026, 10, 2)))
        self.assertTrue(self.triage.picked_on_or_before("a.md", "2026-10-01"))
        self.assertFalse(self.triage.picked_on_or_before("a.md", dt.date(2026, 9, 30)))
        self.assertFalse(self.triage.picked_on_or_before("z.md", dt.date(2026, 10, 2)))

    def test_notes_en_ombre_candidats_et_paires(self):
        self.note("a.md")
        self.note("b.md", url="")
        self.note("c.md", complete=False)
        self.note("d.md", criteria=None, substance=None)
        self.assertEqual([c["file"] for c in self.triage.shadow_candidates("en", "h1")], ["a.md", "b.md"])
        ombre = dict(language="en", model="m", prompts_hash="h1", criteria={"these": False}, substance=0, is_compilation=False,
                     in_themes=True, is_promo=None, scored_at=MIDI)
        self.triage.put_shadow(url="https://a.test/a.md", **ombre)
        self.triage.put_shadow(url="b.md", **ombre)             # clé de repli : le nom du fichier
        self.assertEqual(self.triage.shadow_candidates("en", "h1"), [])
        self.assertEqual([c["file"] for c in self.triage.shadow_candidates("en", "h2")], ["a.md", "b.md"])
        self.assertEqual([c["file"] for c in self.triage.shadow_candidates("fr", "h1")], ["a.md", "b.md"])
        self.triage.put_shadow(url="b.md", **{**ombre, "substance": 4})      # remplace la ligne
        paires = self.triage.shadow_pairs("en")
        self.assertEqual([p["file"] for p in paires], ["a.md", "b.md"])
        self.assertEqual(paires[0]["en"], {"criteria": {"these": False}, "substance": 0, "is_compilation": False, "in_themes": True,
                                           "is_promo": None})
        self.assertEqual(paires[0]["fr"]["criteria"], {"these": True, "etaye": False})
        self.assertEqual(paires[1]["en"]["substance"], 4)
        lignes = self.triage.shadow_rows()
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]["scored_at"], MIDI)

    def test_calibration_valeurs_avis_et_reexport(self):
        self.note("a.md", title="Titre A")
        entrees = [dict(file="a.md", verdict="keep", relevance=80, substance=4, in_themes=True, is_compilation=False, is_promo=False,
                        missing="aucune source"),
                   dict(file="b.md", verdict="discard", relevance=None, substance=None)]
        self.triage.refresh_calibration(entrees, MIDI)
        self.assertEqual(self.triage.calibration_opinions(), {})
        compte = self.triage.apply_opinions({"a.md": True, "b.md": False, "zz.md": True, "c.md": None})
        self.assertEqual(compte, {"keep": 1, "discard": 1, "cleared": 0, "unknown": 2})
        self.assertEqual(self.triage.calibration_opinions(), {"a.md": True, "b.md": False})
        # nouvel export : valeurs rafraîchies, avis conservés
        self.triage.refresh_calibration([dict(entrees[0], relevance=10)], MIDI + dt.timedelta(days=1))
        lignes = {l["file"]: l for l in self.triage.calibration_entries()}
        self.assertEqual(lignes["a.md"]["relevance"], 10)
        self.assertEqual(lignes["a.md"]["exported_at"], MIDI + dt.timedelta(days=1))
        self.assertEqual(lignes["a.md"]["opinion"], "keep")
        self.assertEqual(lignes["a.md"]["title"], "Titre A")
        self.assertEqual(lignes["b.md"]["title"], "b.md")          # plus de note : le nom du fichier tient lieu de titre
        self.assertEqual((lignes["b.md"]["relevance"], lignes["b.md"]["opinion"]), (None, "discard"))
        self.assertIs(lignes["a.md"]["in_themes"], True)
        self.assertEqual(self.triage.apply_opinions({"a.md": None}), {"keep": 0, "discard": 0, "cleared": 1, "unknown": 0})
        self.assertEqual(self.triage.calibration_opinions(), {"b.md": False})
        self.assertEqual(self.triage.apply_opinions({"a.md": None}), {"keep": 0, "discard": 0, "cleared": 0, "unknown": 0})
        self.assertIsNone({l["file"]: l for l in self.triage.calibration_entries()}["a.md"]["opinion_at"])

    def test_validation_et_annulation(self):
        self.watch.add_article("https://a.test/1", "a.test", "T", "f.md", None, True, MIDI)
        self.watch.commit()
        self.watch.add_article("https://a.test/2", "a.test", "U", "g.md", None, True, MIDI)
        self.watch.rollback()
        self.assertEqual([a["url"] for a in self.watch.articles()], ["https://a.test/1"])


class ContratFaux(Contrat, unittest.TestCase):
    def ouvrir(self, readonly=False):
        self.donnees = fake_store.FakeData()
        return self.donnees.open_watch(), self.donnees.open_triage()

    def test_le_faux_garde_les_roles_demandes_et_refuse_une_base_eteinte(self):
        self.donnees.open_watch(readonly=True)
        self.assertEqual(self.donnees.roles, ["rw", "rw", "ro"])
        self.donnees.unavailable = ws.WatchDatabaseUnavailable("OperationalError")
        with self.assertRaises(ws.WatchDatabaseUnavailable):
            self.donnees.open_triage()

    def test_le_faux_fait_echouer_la_validation_sur_demande(self):
        self.watch.add_article("https://a.test/1", "a.test", "T", "f.md", None, True, MIDI)
        self.donnees.fail_on_commit(1)
        with self.assertRaises(ws.WatchDatabaseUnavailable):
            self.watch.commit()
        self.assertEqual(self.watch.articles(), [])


class ContratPostgres(Contrat, unittest.TestCase):
    def ouvrir(self, readonly=False):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.ouvertes = []
        c = self._connexion()
        db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()
        return ws.open_watch_store(connect=self._connect), ws.open_triage_store(connect=self._connect)

    def _connexion(self):
        c = db.connect(base.url_vers(self.nom_base), password=base.MOT_DE_PASSE)
        self.ouvertes.append(c)
        return c

    def _connect(self, role, dbname):
        c = self._connexion()
        if role:
            c.execute(f"SET ROLE {role}")
            c.commit()
        return c

    def _supprimer(self):
        for c in self.ouvertes:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def test_ouverture_en_lecture_seule_refuse_l_ecriture(self):
        lecture = ws.open_triage_store(readonly=True, connect=self._connect)
        self.assertEqual(lecture.score_files(), set())
        with self.assertRaises(Exception):
            lecture.add_picks("2026-10-01", ["a.md"])
        lecture.rollback()


class _FausseConnexion:
    def __init__(self, present):
        self.present = present
        self.closed = False

    def execute(self, sql, params=()):
        resultat = self

        class R:
            def fetchall(inner):
                return [(t,) for t in resultat.present]
        return R()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class ModuleSansRepli(unittest.TestCase):
    """Statique : aucun stockage local de repli dans le magasin ni dans les deux scripts."""

    # Les scripts entrent dans cette liste quand ils passent sur la base (groupes 3 et 5 du change) ; le module, dès maintenant.
    SANS_REPLI = ("watch_store.py", "watch_lab.py", "watch_triage.py")

    def test_aucune_trace_de_sqlite(self):
        for nom in self.SANS_REPLI:
            texte = (RACINE / "tools" / nom).read_text(encoding="utf-8")
            with self.subTest(fichier=nom):
                self.assertNotRegex(texte, r"(?i)sqlite")

    def test_tables_absentes_et_base_eteinte(self):
        with self.assertRaises(ws.WatchTablesMissing):
            ws.open_watch_store(connect=lambda role, dbname: _FausseConnexion(present=[]))
        with self.assertRaises(ws.WatchDatabaseUnavailable):
            ws.open_watch_store(connect=lambda role, dbname: (_ for _ in ()).throw(ConnectionError("mot de passe: secret")))

    def test_erreurs_sans_secret(self):
        with self.assertRaises(ws.WatchDatabaseUnavailable) as contexte:
            ws.open_watch_store(connect=lambda role, dbname: (_ for _ in ()).throw(ConnectionError("password=hunter2 host=10.0.0.1")))
        self.assertEqual(str(contexte.exception), "ConnectionError")
        self.assertNotIn("hunter2", repr(contexte.exception))

    def test_les_deux_roles_sont_demandes(self):
        demandes = []

        def connect(role, dbname):
            demandes.append((role, dbname))
            return _FausseConnexion(present=list(ws.TABLES))

        ws.open_watch_store(readonly=True, connect=connect)
        ws.open_triage_store(connect=connect)
        self.assertEqual(demandes, [("pmzilla_knowledge_ro", None), (None, None)])

    def test_les_onze_tables_sont_celles_de_la_migration(self):
        migration = (RACINE / "db" / "migrations" / "0007_knowledge_watch_triage.sql").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"CREATE TABLE knowledge\.(\w+)", migration)), set(ws.TABLES))


if __name__ == "__main__":
    unittest.main()
