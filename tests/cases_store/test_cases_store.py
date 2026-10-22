"""
Tests de tools/cases_store.py : couche d'accès du module des cas (db-lot2, groupe 5).

    bash tests/run_all.sh cases_store

Sans base (fausse connexion, faux embedding) : validation des brouillons, refus avant toute connexion (liste des noms absente ou vide),
durées, auteur, bornes, seuil non calibré, pannes d'embedding, connect_cases, lecteur paresseux. Avec base jetable pmzilla_test_<hex>
(classe sautée sans PMZILLA_LAB_DB_PASSWORD, comme tests/db et tests/hybrid_search) : écritures, lectures, recherche sur des lignes inventées.
Données inventées uniquement : auteurs `agile-lead-test` et `agile-lead-b`, nom « sensible » inventé, jamais le vrai identifiant.
"""
import contextlib
import datetime as dt
import math
import os
import re
import secrets
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "db"))
import cases_store as cs        # noqa: E402
import sensitive_names as sn    # noqa: E402
import test_db as base          # noqa: E402  (connexion, base jetable, mot de passe ; sans effet sur les schémas réels)
from test_db import db          # noqa: E402

TODAY = dt.date(2027, 3, 1)
NOMS = ["Quxlorian", "ABCD"]            # liste inventée
ME, OTHER = "agile-lead-test", "agile-lead-b"


def draft(**over):
    valeurs = {"problem": "Les parties prenantes ne viennent plus aux revues de sprint",
               "context": {"team_type": "type A", "team_size": 7, "phase": "croissance"},
               "tested": "Une revue construite autour de deux décisions", "expected_signal": "Les parties prenantes reviennent",
               "success_criterion": "Quatre revues de suite avec au moins trois parties prenantes"}
    valeurs.update(over)
    return valeurs


class FauxCurseur:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append(sql)

    def fetchone(self):
        return self.conn.fetch.pop(0) if self.conn.fetch else None

    def fetchall(self):
        return []


class FausseConnexion:
    """Ni appelable ni réelle : enregistre ce qu'on lui demande. `fetch` : lignes rendues, dans l'ordre, par fetchone."""

    def __init__(self, fetch=()):
        self.executed, self.fetch, self.commits, self.rollbacks = [], list(fetch), 0, 0

    def cursor(self):
        return FauxCurseur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def ecrit(self):
        return [s for s in self.executed if re.match(r"\s*(INSERT|UPDATE|DELETE)", s)]


class Ouvreur:
    """Fonction qui ouvre une connexion : compte ses appels (aucun avant les refus qui ne demandent pas la base)."""

    def __init__(self, conn=None):
        self.appels, self.conn = 0, conn or FausseConnexion()

    def __call__(self):
        self.appels += 1
        return self.conn


class Embedding:
    def __init__(self, erreur=None):
        self.appels, self.erreur = [], erreur

    def __call__(self, texte):
        self.appels.append(texte)
        if self.erreur:
            raise self.erreur
        return [1.0] + [0.0] * 1023


class AvecDossier(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dossier = Path(self.temp.name)

    def liste(self, contenu, nom="noms.txt"):
        chemin = self.dossier / nom
        chemin.write_text(contenu, encoding="utf-8")
        return chemin


# ---------------------------------------------------------------------------
# Sans base
# ---------------------------------------------------------------------------

class Import(unittest.TestCase):
    def test_import_sans_connexion_ni_module_lourd(self):
        code = ("import sys; sys.path.insert(0, %r); import cases_store; "
                "lourds = [m for m in ('numpy', 'httpx', 'yaml', 'psycopg', 'db', 'pmzilla_lab_library') if m in sys.modules]; "
                "assert not lourds, lourds") % str(RACINE / "tools")
        fait = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True)
        self.assertEqual(fait.returncode, 0, fait.stderr)

    def test_constantes(self):
        self.assertEqual((cs.DEFAULT_REVIEW_WEEKS, cs.MAX_POSTPONEMENTS, cs.DEFAULT_LIMIT, cs.MAX_LIMIT), (6, 2, 3, 10))
        self.assertIsInstance(cs.MIN_SIMILARITY, float)
        self.assertTrue(0 < cs.MIN_SIMILARITY < 1)

    def test_longueur_max_vient_de_cases_store(self):
        import journal_lab
        self.assertEqual(cs.MAX_TEXT_LENGTH, 600)
        self.assertEqual(journal_lab.LONGUEUR_MAX, cs.MAX_TEXT_LENGTH)


class ValidationDuLancement(unittest.TestCase):
    def valider(self, **over):
        return cs.validate_start_draft(draft(**over), TODAY, NOMS)

    def refus(self, code, field=None, **over):
        with self.assertRaises(cs.CasesError) as e:
            self.valider(**over)
        self.assertEqual(e.exception.code, code)
        if field:
            self.assertEqual(e.exception.field, field)
        return str(e.exception)

    def test_brouillon_valide_et_review_par_defaut(self):
        propre = self.valider()
        self.assertEqual(propre["started_on"], TODAY)
        self.assertEqual(propre["review_due"], TODAY + dt.timedelta(weeks=6))
        self.assertEqual(propre["context"], {"team_type": "type A", "team_size": "7", "phase": "croissance"})
        self.assertIsNone(propre["posture"])

    def test_cle_inconnue_nommee(self):
        message = self.refus("unknown_key", "coucou", coucou="x")
        self.assertIn("coucou", message)

    def test_champs_obligatoires(self):
        for champ in ("problem", "context", "tested", "expected_signal", "success_criterion"):
            with self.subTest(champ=champ):
                brouillon = draft()
                del brouillon[champ]
                with self.assertRaises(cs.CasesError) as e:
                    cs.validate_start_draft(brouillon, TODAY, NOMS)
                self.assertEqual((e.exception.code, e.exception.field), ("field_missing", champ))
        self.refus("field_missing", "problem", problem="   ")

    def test_dates(self):
        self.refus("date_future", "date", date=TODAY + dt.timedelta(days=1))
        self.refus("date_past", "review_due", review_due=TODAY - dt.timedelta(days=1))
        self.refus("date_invalid", "date", date="pas une date")
        self.assertEqual(self.valider(date="2027-02-01")["review_due"], dt.date(2027, 2, 1) + dt.timedelta(weeks=6))
        self.assertEqual(self.valider(review_due="2027-03-01")["review_due"], TODAY)

    def test_contexte(self):
        self.refus("unknown_key", "context", context={"team_type": "A", "ville": "X"})
        self.refus("field_missing", "context", context={})
        self.refus("field_type", "context", context="équipe")
        self.refus("field_type", "context.phase", context={"phase": ["a"]})

    def test_types_de_liste(self):
        self.refus("field_type", "hypotheses", hypotheses="une seule")
        self.refus("field_type", "references_used", references_used={"a": 1})
        self.refus("field_type", "hypotheses", hypotheses=[["x"]])
        self.assertEqual(self.valider(hypotheses=["a", "b"])["hypotheses"], ["a", "b"])

    def test_posture(self):
        self.assertEqual(self.valider(posture="none")["posture"], "none")
        self.refus("field_value", "posture", posture="agility")

    def test_longueur(self):
        self.assertTrue(self.valider(problem="x" * cs.MAX_TEXT_LENGTH))
        self.refus("field_too_long", "problem", problem="x" * (cs.MAX_TEXT_LENGTH + 1))
        self.refus("field_too_long", "hypotheses", hypotheses=["ok", "y" * (cs.MAX_TEXT_LENGTH + 1)])
        self.refus("field_too_long", "context.phase", context={"phase": "z" * (cs.MAX_TEXT_LENGTH + 1)})

    def test_nom_sensible_refuse_sans_etre_nomme(self):
        for champ, valeur in (("problem", "Le client Quxlorian bloque"), ("hypotheses", ["rien", "chez quxlorian"]),
                              ("context", {"team_type": "équipe ABCD"})):
            with self.subTest(champ=champ):
                with self.assertRaises(cs.CasesError) as e:
                    self.valider(**{champ: valeur})
                self.assertEqual(e.exception.code, "sensitive_name")
                self.assertTrue(e.exception.field.startswith(champ))
                self.assertNotIn("quxlorian", str(e.exception).lower())
                self.assertNotIn("abcd", str(e.exception).lower())

    def test_nom_colle_a_d_autres_lettres_accepte(self):
        self.assertTrue(self.valider(problem="Les Quxloriannes et abcdef et Abcd2"))


class ValidationNoteEtCloture(unittest.TestCase):
    def test_note(self):
        self.assertEqual(cs.validate_note_draft({"note": " ok "}, TODAY, NOMS), {"note": "ok", "noted_on": TODAY})
        for brouillon, code in (({}, "field_missing"), ({"note": "x", "autre": 1}, "unknown_key"),
                                ({"note": "x", "date": TODAY + dt.timedelta(days=1)}, "date_future"),
                                ({"note": "voir Quxlorian"}, "sensitive_name"), ({"note": "y" * 601}, "field_too_long")):
            with self.subTest(brouillon=brouillon), self.assertRaises(cs.CasesError) as e:
                cs.validate_note_draft(brouillon, TODAY, NOMS)
            self.assertEqual(e.exception.code, code)

    def test_cloture(self):
        propre = cs.validate_close_draft({"outcome": "worked", "confidence": "medium"}, TODAY, NOMS)
        self.assertEqual((propre["outcome"], propre["confidence"], propre["reviewed_on"]), ("worked", "medium", TODAY))
        self.assertEqual(cs.validate_close_draft({"outcome": "dropped", "drop_reason": "plus de budget"}, TODAY, NOMS)["drop_reason"],
                         "plus de budget")
        refus = (({}, "field_missing"), ({"outcome": "gagné"}, "field_value"), ({"outcome": "worked", "confidence": "sure"}, "field_value"),
                 ({"outcome": "dropped"}, "field_missing"), ({"outcome": "worked", "drop_reason": "x"}, "field_value"),
                 ({"outcome": "worked", "inconnue": 1}, "unknown_key"), ({"outcome": "worked", "date": TODAY + dt.timedelta(days=1)}, "date_future"),
                 ({"outcome": "failed", "what_got_stuck": "bloqué chez Quxlorian"}, "sensitive_name"))
        for brouillon, code in refus:
            with self.subTest(brouillon=brouillon), self.assertRaises(cs.CasesError) as e:
                cs.validate_close_draft(brouillon, TODAY, NOMS)
            self.assertEqual(e.exception.code, code)

    def test_date_de_bilan_contre_le_lancement(self):
        with self.assertRaises(cs.CasesError) as e:
            cs.validate_close_draft({"outcome": "worked", "date": "2027-01-01"}, TODAY, NOMS, started_on=dt.date(2027, 2, 1))
        self.assertEqual(e.exception.code, "date_before_start")


class ListeDesNomsAbsenteOuVide(AvecDossier):
    """Refus avant toute connexion, pour start, note et close (design.md 3.5, décision de l'utilisateur)."""

    def appels(self, chemin):
        ouvreur, embed = Ouvreur(), Embedding()
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(chemin)}):
            yield "start", lambda: cs.start_experiment(ouvreur, embed, draft(), ME, TODAY)
            yield "note", lambda: cs.add_note(ouvreur, 1, "une note", None, ME, today=TODAY)
            yield "close", lambda: cs.close_experiment(ouvreur, 1, {"outcome": "worked"}, ME, TODAY)
        self.assertEqual((ouvreur.appels, embed.appels, ouvreur.conn.executed), (0, [], []))

    def verifier(self, chemin, raison):
        for nom, appel in self.appels(chemin):
            with self.subTest(commande=nom), self.assertRaises(sn.SensitiveNamesUnavailable) as e:
                appel()
            self.assertEqual(e.exception.reason, raison)
            self.assertIn(str(chemin), str(e.exception))

    def test_liste_absente(self):
        self.verifier(self.dossier / "absente.txt", "missing")

    def test_liste_sans_aucun_nom(self):
        self.verifier(self.liste("# commentaire\n\n"), "empty")
        self.verifier(self.liste("", "vide.txt"), "empty")

    def test_postpone_et_drop_ne_lisent_pas_la_liste(self):
        ouvreur = Ouvreur(FausseConnexion([("agile-lead-test", "running", dt.date(2027, 1, 1)), (0,)]))
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.dossier / "absente.txt")}):
            self.assertEqual(cs.postpone(ouvreur, 1, "2w", ME, TODAY)["postponements"], 1)
            ouvreur.conn.fetch.append((ME, "running", dt.date(2027, 1, 1)))
            cs.drop(ouvreur, 1, ME)

    def test_liste_donnee_non_lue(self):
        ouvreur = Ouvreur(FausseConnexion([(ME, "running", dt.date(2027, 1, 1))]))
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.dossier / "absente.txt")}):
            cs.add_note(ouvreur, 1, "une note", None, ME, today=TODAY, names=NOMS)
        self.assertEqual(ouvreur.conn.commits, 1)


class ReglesDesEcrituresSansBase(unittest.TestCase):
    def conn(self, *lignes):
        return FausseConnexion(lignes)

    def test_troisieme_report_refuse(self):
        conn = self.conn((ME, "running", dt.date(2027, 1, 1)), (cs.MAX_POSTPONEMENTS,))
        with self.assertRaises(cs.CasesError) as e:
            cs.postpone(conn, 4, "1w", ME, TODAY)
        self.assertEqual(e.exception.code, "postponement_limit")
        self.assertIn("close", str(e.exception))
        self.assertIn("drop", str(e.exception))
        self.assertEqual((conn.ecrit(), conn.commits, conn.rollbacks), ([], 0, 1))

    def test_report_calcule_la_date_et_compte(self):
        conn = self.conn((ME, "running", dt.date(2027, 1, 1)), (1,))
        self.assertEqual(cs.postpone(conn, 4, "10d", ME, TODAY), {"review_due": "2027-03-11", "postponements": 2})
        self.assertEqual(len(conn.ecrit()), 1)

    def test_experience_d_un_autre_auteur_ou_close_ou_inconnue(self):
        for ligne, code in (((OTHER, "running", TODAY), "not_author"), ((ME, "closed", TODAY), "not_running"), (None, "unknown_experiment")):
            conn = self.conn(*([ligne] if ligne else []))
            for appel in (lambda: cs.drop(conn, 7, ME), lambda: cs.postpone(conn, 7, "1w", ME, TODAY),
                          lambda: cs.add_note(conn, 7, "x", None, ME, today=TODAY, names=NOMS)):
                conn.fetch[:] = [ligne] if ligne else []
                with self.subTest(code=code), self.assertRaises(cs.CasesError) as e:
                    appel()
                self.assertEqual(e.exception.code, code)
            self.assertEqual((conn.ecrit(), conn.commits), ([], 0))

    def test_note_avant_le_lancement_refusee(self):
        conn = self.conn((ME, "running", dt.date(2027, 2, 10)))
        with self.assertRaises(cs.CasesError) as e:
            cs.add_note(conn, 1, "x", dt.date(2027, 2, 1), ME, today=TODAY, names=NOMS)
        self.assertEqual(e.exception.code, "date_before_start")
        self.assertEqual(conn.ecrit(), [])

    def test_duree(self):
        for texte, jours in (("1d", 1), ("10d", 10), ("1w", 7), ("2w", 14)):
            self.assertEqual(cs.parse_duration(texte), jours)
        for texte in ("0d", "0w", "2", "w", "2 w", "2W", "-1w", "1.5w", "2m", "02w", "", None, 2):
            with self.subTest(texte=texte), self.assertRaises(cs.CasesError) as e:
                cs.parse_duration(texte)
            self.assertEqual(e.exception.code, "duration_invalid")

    def test_numero_et_auteur_invalides(self):
        for numero in (0, -1, "1", None, True):
            with self.subTest(numero=numero), self.assertRaises(cs.CasesError):
                cs.drop(self.conn(), numero, ME)
        for auteur in (None, "", "  "):
            with self.subTest(auteur=auteur), self.assertRaises(cs.CasesError):
                cs.drop(self.conn(), 1, auteur)

    def test_erreur_de_la_base_sans_la_ligne_refusee(self):
        class ErreurBase(Exception):
            sqlstate = "23514"
        ErreurBase.__module__ = "psycopg.errors"

        class Conn(FausseConnexion):
            def cursor(self):
                raise ErreurBase('Failing row contains (Quxlorian)')
        conn = Conn()
        with self.assertRaises(cs.CasesError) as e:
            cs.drop(conn, 1, ME)
        self.assertEqual(e.exception.code, "database_refused")
        self.assertNotIn("Quxlorian", str(e.exception))
        self.assertIn("23514", str(e.exception))
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))


class Auteur(AvecDossier):
    def fichier(self, contenu):
        (self.dossier / ".pmzilla").mkdir(exist_ok=True)
        (self.dossier / ".pmzilla" / "cases.yaml").write_text(contenu, encoding="utf-8")

    def test_ordre_de_resolution(self):
        self.fichier("author: agile-lead-fichier\n")
        self.assertEqual(cs.resolve_author(self.dossier, {AUTEUR: " agile-lead-env "}), "agile-lead-env")
        self.assertEqual(cs.resolve_author(self.dossier, {AUTEUR: "   "}), "agile-lead-fichier")
        self.assertEqual(cs.resolve_author(self.dossier, {AUTEUR: ""}), "agile-lead-fichier")
        self.assertEqual(cs.resolve_author(self.dossier, {}), "agile-lead-fichier")

    def test_aucun_auteur(self):
        self.assertIsNone(cs.resolve_author(self.dossier, {}))
        self.fichier("author:   # rien\n")
        self.assertIsNone(cs.resolve_author(self.dossier, {AUTEUR: " "}))
        self.fichier("autre: x\n")
        self.assertIsNone(cs.resolve_author(self.dossier, {}))
        self.fichier("author: [illisible\n")
        self.assertIsNone(cs.resolve_author(self.dossier, {}))

    def test_le_fichier_passe_par_le_registre_de_lab_paths(self):
        # Décision du 2026-10-21, point 8 (A9) : le chemin vient de lab_paths.LOCAL_FILES["cases_author"], jamais d'un calcul local.
        (self.dossier / "ailleurs").mkdir()
        (self.dossier / "ailleurs" / "auteur.yaml").write_text("author: agile-lead-registre\n", encoding="utf-8")
        with mock.patch.dict(cs.lab_paths.LOCAL_FILES, {"cases_author": (("ailleurs", "auteur.yaml"), ())}):
            self.assertEqual(cs.resolve_author(self.dossier, {}), "agile-lead-registre")
            with mock.patch.object(cs, "default_workspace", return_value=self.dossier):
                self.assertEqual(cs.resolve_author(None, {}), "agile-lead-registre")

    def test_refus_qui_nomme_le_fichier(self):
        with self.assertRaises(cs.CasesError) as e:
            cs.require_author(self.dossier, {})
        self.assertIn(".pmzilla/cases.yaml", str(e.exception))
        self.assertEqual(e.exception.code, "author_missing")

    def test_refus_nomme_le_fichier_du_registre(self):
        # revue du 2026-10-21 : le nom du fichier dans le refus vient du registre de lab_paths, jamais d'une constante qui le double
        with mock.patch.dict(cs.lab_paths.LOCAL_FILES, {"cases_author": (("ailleurs", "auteur.yaml"), ())}):
            with self.assertRaises(cs.CasesError) as e:
                cs.require_author(self.dossier, {})
        self.assertIn("ailleurs/auteur.yaml", str(e.exception))
        self.assertEqual(e.exception.field, "ailleurs/auteur.yaml")
        self.assertFalse(hasattr(cs, "AUTHOR_FILE"))
        self.fichier("author: agile-lead-fichier\n")
        self.assertEqual(cs.require_author(self.dossier, {}), "agile-lead-fichier")

    def test_espace_de_travail_par_defaut_de_la_variable(self):
        self.fichier("author: agile-lead-fichier\n")
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_WORKSPACE": str(self.dossier), AUTEUR: ""}):
            self.assertEqual(cs.resolve_author(), "agile-lead-fichier")


AUTEUR = "PMZILLA_LAB_CASES_AUTHOR"


class RegleDeLaRevueDue(unittest.TestCase):
    """Une revue est due quand review_due <= aujourd'hui : une seule règle pour le lecteur MCP, le journal et le tableau de bord."""

    def test_is_due_cas_limite_le_jour_meme(self):
        hier, jour, demain = dt.date(2027, 2, 28), dt.date(2027, 3, 1), dt.date(2027, 3, 2)
        self.assertEqual([cs.is_due(d, jour) for d in (hier, jour, demain)], [True, True, False])

    def test_running_experiments_signale_due_la_revue_du_jour(self):
        lignes = [(1, "p1", dt.date(2027, 1, 4), dt.date(2027, 2, 28), 0), (2, "p2", dt.date(2027, 1, 4), dt.date(2027, 3, 1), 0),
                  (3, "p3", dt.date(2027, 1, 4), dt.date(2027, 3, 2), 0)]
        with mock.patch.object(cs, "_read", return_value=lignes):
            rendu = cs.running_experiments(object(), ME, dt.date(2027, 3, 1))
        self.assertEqual([(r["number"], r["due"]) for r in rendu], [(1, True), (2, True), (3, False)])
        self.assertTrue(all("overdue" not in r for r in rendu))

    def test_due_reviews_et_running_experiments_partagent_la_condition(self):
        vus = []

        def lire(conn, sql, params=()):
            vus.append(sql)
            return []
        with mock.patch.object(cs, "_read", lire):
            cs.due_reviews(object(), ME, dt.date(2027, 3, 1))
        self.assertIn(cs.DUE_CONDITION, vus[0])
        self.assertEqual(cs.DUE_CONDITION, "review_due <= %s")


class RechercheSansBase(unittest.TestCase):
    def test_bornes_de_limite(self):
        self.assertEqual([cs._limit(n) for n in (1, 3, 10, 11, 500, 0, -4)], [1, 3, 10, 10, 10, 1, 1])
        for mauvais in ("3", None, 2.5, True):
            with self.subTest(limite=mauvais), self.assertRaises(cs.CasesError):
                cs._limit(mauvais)

    def test_seuil_non_calibre_refuse_les_deux_recherches(self):
        embed, conn = Embedding(), FausseConnexion()
        with mock.patch.object(cs, "MIN_SIMILARITY", None):
            for appel in (lambda: cs.search_cases(conn, embed, "une question"),
                          lambda: cs.search_experiments(conn, embed, "une question", ME)):
                with self.assertRaises(cs.CasesError) as e:
                    appel()
                self.assertEqual(e.exception.code, "threshold_not_calibrated")
            self.assertIn("not calibrated", str(e.exception))
        self.assertEqual((embed.appels, conn.executed), ([], []))

    def test_question_vide(self):
        with mock.patch.object(cs, "MIN_SIMILARITY", 0.5):
            for question in ("", "   ", None):
                with self.subTest(question=question), self.assertRaises(cs.CasesError) as e:
                    cs.search_cases(FausseConnexion(), Embedding(), question)
                self.assertEqual(e.exception.code, "query_empty")

    def test_panne_d_embedding_pendant_la_recherche(self):
        with mock.patch.object(cs, "MIN_SIMILARITY", 0.5), self.assertRaises(cs.CasesError) as e:
            cs.search_cases(FausseConnexion(), Embedding(SystemExit("pas de modèle")), "question")
        self.assertEqual(e.exception.code, "embedding_unavailable")

    def test_specifications_sans_tsvector_ni_filtre(self):
        import hybrid_search
        for spec in (cs.CASES_SPEC, cs.EXPERIMENTS_SPEC):
            sql, params = hybrid_search.build_query(spec, query="une revue", vector=[1.0, 0.0], today=TODAY, limit=cs.MAX_LIMIT)
            self.assertIn("NULL::tsvector AS tsv", sql)
            self.assertIn("|||", sql)
            self.assertNotIn("collections", params)
        self.assertIn("status = 'running'", hybrid_search.build_query(cs.EXPERIMENTS_SPEC, query="x", vector=[1.0], today=TODAY)[0])
        with self.assertRaises(ValueError):
            hybrid_search.build_query(cs.CASES_SPEC, query="x", vector=[1.0], fulltext="tsvector")


class PannesDEmbedding(unittest.TestCase):
    def essayer(self, erreur):
        ouvreur, embed = Ouvreur(), Embedding(erreur)
        with self.assertRaises(cs.CasesError) as e:
            cs.start_experiment(ouvreur, embed, draft(), ME, TODAY, names=NOMS)
        self.assertEqual(e.exception.code, "embedding_unavailable")
        self.assertIn("embedding service must run", str(e.exception))
        self.assertEqual((ouvreur.appels, ouvreur.conn.executed, ouvreur.conn.commits), (0, [], 0))

    def test_ollama_ne_connait_pas_le_modele(self):
        self.essayer(SystemExit("Ollama does not know the model"))

    def test_ollama_ne_repond_pas(self):
        import httpx
        self.essayer(httpx.ConnectError("refused"))
        self.essayer(httpx.ReadTimeout("slow"))

    def test_autre_erreur_non_masquee(self):
        with self.assertRaises(ZeroDivisionError):
            cs.start_experiment(Ouvreur(), Embedding(ZeroDivisionError()), draft(), ME, TODAY, names=NOMS)

    def test_default_embed_appelle_la_bibliotheque_a_l_usage(self):
        import numpy as np
        import pmzilla_lab_library
        with mock.patch.object(pmzilla_lab_library, "embed", return_value=np.array([[0.0, 1.0]])) as faux:
            self.assertEqual(list(cs.default_embed("texte")), [0.0, 1.0])
        faux.assert_called_once_with(["texte"])


class ConnectCases(unittest.TestCase):
    def test_nom_de_base_et_delai(self):
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_CASES_DBNAME": "pmzilla_eval_xyz"}), mock.patch.object(db, "connect") as faux:
            cs.connect_cases("pmzilla_cases_ro", timeout=2)
        faux.assert_called_once_with(role="pmzilla_cases_ro", dbname="pmzilla_eval_xyz", timeout=2)

    def test_sans_variable_ou_vide_meme_base_et_delai_par_defaut(self):
        for valeur in (None, ""):
            env = {k: v for k, v in os.environ.items() if k != "PMZILLA_LAB_CASES_DBNAME"}
            if valeur is not None:
                env["PMZILLA_LAB_CASES_DBNAME"] = valeur
            with self.subTest(valeur=valeur), mock.patch.dict(os.environ, env, clear=True), mock.patch.object(db, "connect") as faux:
                cs.connect_cases("pmzilla_cases")
            faux.assert_called_once_with(role="pmzilla_cases", dbname=None, timeout=db.DELAI_CONNEXION)


class LecteurParesseux(unittest.TestCase):
    def test_aucune_connexion_a_la_construction(self):
        ouvreur = Ouvreur()
        reader = cs.CasesReader(connect=ouvreur, embed=Embedding())
        self.assertEqual(ouvreur.appels, 0)
        reader.connection()
        reader.connection()
        self.assertEqual(ouvreur.appels, 1)

    def test_une_reprise_si_la_connexion_est_tombee(self):
        class OperationalError(Exception):
            pass
        ouvreur = Ouvreur()
        reader = cs.CasesReader(connect=ouvreur)
        essais = []

        def fonction(conn):
            essais.append(conn)
            if len(essais) == 1:
                raise OperationalError("connexion perdue")
            return "ok"
        self.assertEqual(reader._run(fonction), "ok")
        self.assertEqual((ouvreur.appels, len(essais)), (2, 2))

    def test_deux_pannes_de_suite_remontent(self):
        class OperationalError(Exception):
            pass
        reader = cs.CasesReader(connect=Ouvreur())

        def toujours(conn):
            raise OperationalError("perdue")
        with self.assertRaises(OperationalError):
            reader._run(toujours)

    def test_autre_erreur_sans_reprise(self):
        ouvreur = Ouvreur()
        reader = cs.CasesReader(connect=ouvreur)

        def erreur(conn):
            raise ValueError("autre")
        with self.assertRaises(ValueError):
            reader._run(erreur)
        self.assertEqual(ouvreur.appels, 1)

    def test_base_injoignable_sans_secret_et_vers_db_up(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("Connexion à la base impossible : refus.")):
            with self.assertRaises(cs.CasesError) as e:
                cs.CasesReader().connection()
        self.assertEqual(e.exception.code, "database_unreachable")
        self.assertIn("bash tools/db_up.sh", str(e.exception))

    def test_echeances_sans_auteur_refusees(self):
        with tempfile.TemporaryDirectory() as vide, mock.patch.dict(os.environ, {"PMZILLA_LAB_WORKSPACE": vide, AUTEUR: ""}):
            reader = cs.CasesReader(connect=Ouvreur())
            with self.assertRaises(cs.CasesError) as e:
                reader.list_due_reviews()
        self.assertIn(".pmzilla/cases.yaml", str(e.exception))

    def test_echeances_avec_la_connexion_du_lecteur(self):
        class Curseur(FauxCurseur):
            def fetchall(self):
                return [(5, "un problème", dt.date(2027, 2, 27), 2)]

        class Conn(FausseConnexion):
            def cursor(self):
                return Curseur(self)
        reader = cs.CasesReader(connect=Ouvreur(Conn()), today=TODAY, author=ME)
        self.assertEqual(reader.list_due_reviews(), [{"number": 5, "problem": "un problème", "review_due": "2027-02-27",
                                                      "postponements": 2, "decision_required": True}])


# ---------------------------------------------------------------------------
# Avec base jetable
# ---------------------------------------------------------------------------

def unit(c):
    """Vecteur de 1024 composantes : c·e1 + sqrt(1 - c²)·e2 (produit scalaire exact c avec e1)."""
    return [c, math.sqrt(max(0.0, 1.0 - c * c))] + [0.0] * 1022


E1 = unit(1.0)
E3 = [0.0, 0.0, 1.0] + [0.0] * 1021


def embed_par_marqueur(texte):
    """Faux embedding des lignes du jeu d'essai : le marqueur [cNN] du texte donne le produit scalaire avec e1."""
    return unit(int(re.search(r"\[c(\d+)\]", texte).group(1)) / 100)


def embed_constant(vecteur):
    return lambda texte: vecteur


class AvecBase(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        self.ouvertes = []
        c = self.ouvrir()
        db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()
        self.super = c
        self.writer = self.ouvrir("pmzilla_cases")
        self.reader = self.ouvrir("pmzilla_cases_ro")

    def _supprimer(self):
        for c in self.ouvertes:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def ouvrir(self, role=None):
        c = db.connect(self.url, password=base.MOT_DE_PASSE)
        self.ouvertes.append(c)
        if role:
            c.execute(f"SET ROLE {role}")
            c.commit()      # le SET ROLE survit aux rollback des écritures refusées et des lectures
        return c

    def lire(self, sql, params=()):
        """Lecture hors des rôles (superutilisateur de la base jetable), sur des données déjà validées."""
        self.super.rollback()
        try:
            return self.super.execute(sql, params).fetchall()
        finally:
            self.super.rollback()

    def lancer(self, **over):
        return cs.start_experiment(self.writer, Embedding(), draft(**over), ME, TODAY, names=NOMS)


class Lancement(AvecBase):
    def test_lancement_enregistre_l_embedding_et_la_date_par_defaut(self):
        numero = self.lancer()
        self.assertEqual(numero, 1)
        ligne = self.lire("SELECT author, status, started_on, review_due, postponements, posture, vector_dims(embedding), context->>'team_size' "
                          "FROM cases.experiments")[0]
        self.assertEqual(ligne, (ME, "running", TODAY, TODAY + dt.timedelta(weeks=6), 0, None, 1024, "7"))

    def test_date_de_bilan_et_posture_donnees(self):
        self.lancer(review_due="2027-05-01", posture="facilitation", hypotheses=["h1"], date="2027-02-20")
        ligne = self.lire("SELECT started_on, review_due, posture, hypotheses FROM cases.experiments")[0]
        self.assertEqual(ligne, (dt.date(2027, 2, 20), dt.date(2027, 5, 1), "facilitation", ["h1"]))

    def test_embedding_en_panne_rien_n_est_ecrit(self):
        with self.assertRaises(cs.CasesError):
            cs.start_experiment(self.writer, Embedding(SystemExit("x")), draft(), ME, TODAY, names=NOMS)
        self.assertEqual(self.lire("SELECT count(*) FROM cases.experiments"), [(0,)])

    def test_le_texte_embarque_est_probleme_chemin_et_test(self):
        embed = Embedding()
        cs.start_experiment(self.writer, embed, draft(chosen_path="le chemin"), ME, TODAY, names=NOMS)
        self.assertEqual(embed.appels, [draft()["problem"] + "\nle chemin\n" + draft()["tested"]])

    def test_le_role_lecture_seule_ne_peut_pas_lancer(self):
        with self.assertRaises(cs.CasesError) as e:
            cs.start_experiment(self.reader, Embedding(), draft(), ME, TODAY, names=NOMS)
        self.assertEqual(e.exception.code, "database_refused")
        self.assertEqual(self.lire("SELECT count(*) FROM cases.experiments"), [(0,)])


class NotesReportsAbandons(AvecBase):
    def test_note_puis_affichage(self):
        n = self.lancer()
        cs.add_note(self.writer, n, "datée du jour", dt.date(2027, 3, 1), ME, today=TODAY, names=NOMS)
        cs.add_note(self.writer, n, "même jour", dt.date(2027, 3, 1), ME, today=TODAY, names=NOMS)
        cs.add_note(self.writer, n, "sans date", None, ME, today=TODAY, names=NOMS)
        vue = cs.show_experiment(self.reader, n)
        self.assertEqual([x["note"] for x in vue["notes"]], ["datée du jour", "même jour", "sans date"])
        self.assertEqual([x["noted_on"] for x in vue["notes"]], ["2027-03-01"] * 3)
        self.assertEqual((vue["number"], vue["status"], vue["review_due"], vue["postponements"]), (n, "running", "2027-04-12", 0))
        self.assertEqual(vue["context"]["team_type"], "type A")

    def test_note_refusee(self):
        n = self.lancer()
        for appel, code in ((lambda: cs.add_note(self.writer, n, "x", None, OTHER, today=TODAY, names=NOMS), "not_author"),
                            (lambda: cs.add_note(self.writer, 99, "x", None, ME, today=TODAY, names=NOMS), "unknown_experiment"),
                            (lambda: cs.add_note(self.writer, n, "x", dt.date(2027, 2, 1), ME, today=TODAY, names=NOMS), "date_before_start"),
                            (lambda: cs.add_note(self.writer, n, "x", dt.date(2027, 3, 2), ME, today=TODAY, names=NOMS), "date_future")):
            with self.subTest(code=code), self.assertRaises(cs.CasesError) as e:
                appel()
            self.assertEqual(e.exception.code, code)
        self.assertEqual(self.lire("SELECT count(*) FROM cases.experiment_notes"), [(0,)])

    def test_troisieme_report_refuse(self):
        n = self.lancer()
        self.assertEqual(cs.postpone(self.writer, n, "2w", ME, TODAY), {"review_due": "2027-03-15", "postponements": 1})
        self.assertEqual(cs.postpone(self.writer, n, "3d", ME, TODAY), {"review_due": "2027-03-04", "postponements": 2})
        with self.assertRaises(cs.CasesError) as e:
            cs.postpone(self.writer, n, "1w", ME, TODAY)
        self.assertEqual(e.exception.code, "postponement_limit")
        self.assertEqual(self.lire("SELECT review_due, postponements FROM cases.experiments"), [(dt.date(2027, 3, 4), 2)])

    def test_report_d_un_autre_auteur_refuse(self):
        n = self.lancer()
        with self.assertRaises(cs.CasesError) as e:
            cs.postpone(self.writer, n, "1w", OTHER, TODAY)
        self.assertEqual(e.exception.code, "not_author")

    def test_abandon_sans_cas(self):
        n = self.lancer()
        cs.drop(self.writer, n, ME)
        self.assertEqual(self.lire("SELECT status FROM cases.experiments"), [("dropped",)])
        self.assertEqual(self.lire("SELECT count(*) FROM cases.cases"), [(0,)])
        with self.assertRaises(cs.CasesError) as e:
            cs.drop(self.writer, n, ME)
        self.assertEqual(e.exception.code, "not_running")

    def test_show_numero_inconnu(self):
        with self.assertRaises(cs.CasesError) as e:
            cs.show_experiment(self.reader, 99)
        self.assertIn("99", str(e.exception))

    def test_show_est_lisible_quel_que_soit_l_auteur(self):
        n = cs.start_experiment(self.writer, Embedding(), draft(), OTHER, TODAY, names=NOMS)
        self.assertEqual(cs.show_experiment(self.reader, n)["author"], OTHER)


class Cloture(AvecBase):
    def test_cas_copie_historique_ordonne_embedding_copie(self):
        n = self.lancer(chosen_path="le chemin", hypotheses=["h"], posture="delivery")
        cs.add_note(self.writer, n, "première note", dt.date(2027, 3, 1), ME, today=TODAY, names=NOMS)
        cs.add_note(self.writer, n, "seconde note", dt.date(2027, 3, 1), ME, today=TODAY, names=NOMS)
        numero_cas = cs.close_experiment(self.writer, n, {"outcome": "worked", "confidence": "medium", "what_got_stuck": "rien"},
                                         ME, dt.date(2027, 3, 20), names=NOMS)
        self.assertEqual(numero_cas, 1)
        cas = self.lire("SELECT c.author, c.posture, c.problem, c.chosen_path, c.tested, c.success_criterion, c.launched_on, c.reviewed_on, "
                        "c.outcome, c.confidence, c.what_got_stuck, c.drop_reason, c.hypotheses, c.context->>'phase', c.embedding = e.embedding, "
                        "c.experiment_id FROM cases.cases c JOIN cases.experiments e ON e.id = c.experiment_id")[0]
        self.assertEqual(cas, (ME, "delivery", draft()["problem"], "le chemin", draft()["tested"], draft()["success_criterion"], TODAY,
                               dt.date(2027, 3, 20), "worked", "medium", "rien", None, ["h"], "croissance", True, n))
        self.assertEqual(self.lire("SELECT status FROM cases.experiments"), [("closed",)])

    def test_historique_dans_l_ordre_des_dates_puis_des_notes(self):
        n = self.lancer(date="2027-02-01")
        for jour, texte in (("2027-02-20", "c"), ("2027-02-10", "a"), ("2027-02-10", "b")):
            cs.add_note(self.writer, n, texte, dt.date.fromisoformat(jour), ME, today=TODAY, names=NOMS)
        cs.close_experiment(self.writer, n, {"outcome": "partly"}, ME, TODAY, names=NOMS)
        self.assertEqual(self.lire("SELECT history FROM cases.cases"),
                         [([{"noted_on": "2027-02-10", "note": "a"}, {"noted_on": "2027-02-10", "note": "b"},
                            {"noted_on": "2027-02-20", "note": "c"}],)])

    def test_abandon_instructif_et_sans_raison(self):
        n = self.lancer()
        with self.assertRaises(cs.CasesError):
            cs.close_experiment(self.writer, n, {"outcome": "dropped"}, ME, TODAY, names=NOMS)
        self.assertEqual(self.lire("SELECT status FROM cases.experiments"), [("running",)])
        cs.close_experiment(self.writer, n, {"outcome": "dropped", "drop_reason": "équipe réorganisée"}, ME, TODAY, names=NOMS)
        self.assertEqual(self.lire("SELECT outcome, drop_reason FROM cases.cases"), [("dropped", "équipe réorganisée")])

    def test_autre_auteur_refuse_rien_n_est_cree(self):
        n = self.lancer()
        with self.assertRaises(cs.CasesError) as e:
            cs.close_experiment(self.writer, n, {"outcome": "worked"}, OTHER, TODAY, names=NOMS)
        self.assertEqual(e.exception.code, "not_author")
        self.assertEqual(self.lire("SELECT count(*) FROM cases.cases"), [(0,)])
        self.assertEqual(self.lire("SELECT status FROM cases.experiments"), [("running",)])

    def test_double_cloture_refusee_un_seul_cas(self):
        n = self.lancer()
        cs.close_experiment(self.writer, n, {"outcome": "failed"}, ME, TODAY, names=NOMS)
        with self.assertRaises(cs.CasesError) as e:
            cs.close_experiment(self.writer, n, {"outcome": "worked"}, ME, TODAY, names=NOMS)
        self.assertEqual(e.exception.code, "not_running")
        self.assertEqual(self.lire("SELECT count(*) FROM cases.cases"), [(1,)])

    def test_date_de_bilan_avant_le_lancement_refusee(self):
        n = self.lancer(date="2027-02-10")
        with self.assertRaises(cs.CasesError) as e:
            cs.close_experiment(self.writer, n, {"outcome": "worked", "date": "2027-02-01"}, ME, TODAY, names=NOMS)
        self.assertEqual(e.exception.code, "date_before_start")
        self.assertEqual(self.lire("SELECT count(*) FROM cases.cases"), [(0,)])

    def test_echec_de_l_insertion_laisse_l_experience_en_cours(self):
        n = self.lancer()
        self.super.execute("ALTER TABLE cases.cases ADD CONSTRAINT refus_total CHECK (false)")
        self.super.commit()
        with self.assertRaises(cs.CasesError) as e:
            cs.close_experiment(self.writer, n, {"outcome": "worked"}, ME, TODAY, names=NOMS)
        self.assertEqual(e.exception.code, "database_refused")
        self.assertEqual(self.lire("SELECT count(*) FROM cases.cases"), [(0,)])
        self.assertEqual(self.lire("SELECT status FROM cases.experiments"), [("running",)])


class Echeances(AvecBase):
    def fixer(self, numero, echeance, reports=0):
        """Date de bilan passée : le brouillon la refuse, la base l'accepte (>= date de lancement)."""
        self.writer.execute("UPDATE cases.experiments SET review_due = %s, postponements = %s WHERE id = %s", (echeance, reports, numero))
        self.writer.commit()

    def test_bilans_dus_du_plus_ancien_au_plus_recent(self):
        a, b, c = (self.lancer(date="2027-01-04") for _ in range(3))
        d = cs.start_experiment(self.writer, Embedding(), draft(date="2027-01-04"), OTHER, TODAY, names=NOMS)
        e = self.lancer(date="2027-01-04")
        for numero, echeance, reports in ((a, "2027-03-01", 0), (b, "2027-02-27", 2), (c, "2027-03-08", 0), (d, "2027-03-01", 0),
                                          (e, "2027-03-01", 0)):
            self.fixer(numero, echeance, reports)
        cs.drop(self.writer, e, ME)
        self.assertEqual(cs.due_reviews(self.reader, ME, TODAY), [
            {"number": b, "problem": draft()["problem"], "review_due": "2027-02-27", "postponements": 2, "decision_required": True},
            {"number": a, "problem": draft()["problem"], "review_due": "2027-03-01", "postponements": 0, "decision_required": False}])
        self.assertEqual([x["number"] for x in cs.due_reviews(self.reader, OTHER, TODAY)], [d])
        self.assertEqual(cs.due_reviews(self.reader, ME, dt.date(2027, 1, 1)), [])

    def test_experiences_en_cours_du_tableau_de_bord(self):
        a, b, c = (self.lancer(date="2027-01-04") for _ in range(3))
        for numero, echeance in ((a, "2027-03-08"), (b, "2027-02-20"), (c, "2027-02-01")):
            self.fixer(numero, echeance)
        cs.drop(self.writer, c, ME)
        cs.close_experiment(self.writer, a, {"outcome": "worked"}, ME, TODAY, names=NOMS)
        f = self.lancer(date="2027-01-04")
        self.fixer(f, "2027-03-01", 1)
        self.assertEqual([(x["number"], x["review_due"], x["due"], x["started_on"], x["postponements"])
                          for x in cs.running_experiments(self.reader, ME, TODAY)],
                         [(b, "2027-02-20", True, "2027-01-04", 0), (f, "2027-03-01", True, "2027-01-04", 1)])


FIXTURE = """\
experiments:
  - {author: agile-lead-test, started_on: 2027-01-04, status: running, problem: "experience proche [c90]", tested: "test un",
     context: {team_type: "équipe A"}, expected_signal: "signal", success_criterion: "critère", review_due: 2027-12-31,
     notes: [{noted_on: 2027-01-10, note: "une note"}]}
  - {author: agile-lead-b, started_on: 2027-01-04, status: running, problem: "experience autre auteur [c80]", tested: "test deux",
     context: {phase: "x"}, expected_signal: "signal", success_criterion: "critère"}
  - {author: agile-lead-test, started_on: 2027-01-04, status: closed, problem: "experience close [c95]", tested: "test trois",
     context: {phase: "x"}, expected_signal: "signal", success_criterion: "critère"}
  - {author: agile-lead-test, started_on: 2027-01-04, status: dropped, problem: "experience abandonnee [c85]", tested: "test quatre",
     context: {phase: "x"}, expected_signal: "signal", success_criterion: "critère"}
  - {author: agile-lead-test, started_on: 2027-01-04, status: running, problem: "experience lointaine [c40]", tested: "test cinq",
     context: {phase: "x"}, expected_signal: "signal", success_criterion: "critère"}
  - {author: agile-lead-b, started_on: 2027-01-04, status: running, problem: "experience limite [c60]", tested: "test six",
     context: {phase: "x"}, expected_signal: "signal", success_criterion: "critère"}
cases:
  - {author: agile-lead-b, launched_on: 2026-06-01, reviewed_on: 2026-07-13, problem: "cas tres proche [c90]", chosen_path: "chemin",
     tested: "test", context: {team_type: "équipe B"}, expected_signal: "signal", success_criterion: "critère", outcome: worked,
     confidence: medium, history: [{noted_on: 2026-06-10, note: "avancée"}], posture: facilitation}
  - {author: agile-lead-b, launched_on: 2026-06-01, reviewed_on: 2026-07-13, problem: "cas moyen [c70]", tested: "test",
     context: {phase: "x"}, expected_signal: "signal", success_criterion: "critère", outcome: partly}
  - {author: agile-lead-b, launched_on: 2026-06-01, reviewed_on: 2026-07-13, problem: "cas limite [c60]", tested: "test",
     context: {phase: "x"}, expected_signal: "signal", success_criterion: "critère", outcome: failed, what_got_stuck: "contourné"}
  - {author: agile-lead-b, launched_on: 2026-06-01, reviewed_on: 2026-07-13, problem: "cas lointain [c40]", tested: "test",
     context: {phase: "x"}, expected_signal: "signal", success_criterion: "critère", outcome: dropped, drop_reason: "plus de budget"}
"""
QUESTION = "zzqxj"       # aucun mot en commun avec les lignes : la voie BM25 reste vide, seul le classement sémantique joue


class Recherche(AvecBase):
    def setUp(self):
        super().setUp()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dossier = Path(temp.name)
        self.fichier = self.dossier / "fixture.yaml"
        self.fichier.write_text(FIXTURE, encoding="utf-8")
        self.super.rollback()
        self.assertEqual(cs.load_fixture(self.super, embed_par_marqueur, self.fichier), {"experiments": 6, "cases": 4})
        patcher = mock.patch.object(cs, "MIN_SIMILARITY", 0.5)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_le_fixture_est_charge_sous_le_role_des_cas(self):
        self.assertEqual(self.lire("SELECT count(*) FROM cases.experiments"), [(10,)])
        self.assertEqual(self.lire("SELECT count(*) FROM cases.cases"), [(4,)])
        self.assertEqual(self.lire("SELECT count(*) FROM cases.experiment_notes"), [(1,)])
        self.assertEqual(self.lire("SELECT status, count(*) FROM cases.experiments GROUP BY status ORDER BY status"),
                         [("closed", 5), ("dropped", 1), ("running", 4)])

    def test_le_plus_proche_d_abord_seuil_applique(self):
        hits = cs.search_cases(self.reader, embed_constant(E1), QUESTION, limit=10)
        self.assertEqual([h["problem"] for h in hits], ["cas tres proche [c90]", "cas moyen [c70]", "cas limite [c60]"])
        self.assertEqual([round(h["similarity"], 2) for h in hits], [0.9, 0.7, 0.6])
        self.assertTrue(all(isinstance(h["score"], float) for h in hits))

    def test_ligne_a_04_ecartee_ligne_a_06_gardee(self):
        problemes = [h["problem"] for h in cs.search_cases(self.reader, embed_constant(E1), QUESTION, limit=10)]
        self.assertIn("cas limite [c60]", problemes)
        self.assertNotIn("cas lointain [c40]", problemes)

    def test_limite_par_defaut_et_bornee(self):
        self.assertEqual(len(cs.search_cases(self.reader, embed_constant(E1), QUESTION)), cs.DEFAULT_LIMIT)
        self.assertEqual(len(cs.search_cases(self.reader, embed_constant(E1), QUESTION, limit=1)), 1)
        self.assertEqual(len(cs.search_cases(self.reader, embed_constant(E1), QUESTION, limit=500)), 3)
        with mock.patch.object(cs, "MAX_LIMIT", 2):
            self.assertEqual(len(cs.search_cases(self.reader, embed_constant(E1), QUESTION, limit=500)), 2)

    def test_question_sans_rapport_resultat_vide(self):
        self.assertEqual(cs.search_cases(self.reader, embed_constant(E3), QUESTION), [])
        self.assertEqual(cs.search_experiments(self.reader, embed_constant(E3), QUESTION, ME), [])

    def test_fiche_d_un_cas(self):
        premier = cs.search_cases(self.reader, embed_constant(E1), QUESTION)[0]
        self.assertEqual({k: premier[k] for k in ("author", "launched_on", "reviewed_on", "posture", "chosen_path", "outcome", "confidence",
                                                   "history", "drop_reason", "what_got_stuck", "success_criterion")},
                         {"author": "agile-lead-b", "launched_on": "2026-06-01", "reviewed_on": "2026-07-13", "posture": "facilitation",
                          "chosen_path": "chemin", "outcome": "worked", "confidence": "medium",
                          "history": [{"noted_on": "2026-06-10", "note": "avancée"}], "drop_reason": None, "what_got_stuck": None,
                          "success_criterion": "critère"})
        self.assertEqual(premier["number"], 1)
        self.assertEqual(set(premier), {"number", "context", "hypotheses", "references_used", "tested", "expected_signal", "similarity",
                                        "score", "author", "launched_on", "reviewed_on", "posture", "problem", "chosen_path", "success_criterion",
                                        "history", "outcome", "drop_reason", "what_got_stuck", "confidence"})

    def test_experiences_en_cours_seulement_et_mine(self):
        hits = cs.search_experiments(self.reader, embed_constant(E1), QUESTION, ME, limit=10)
        self.assertEqual([(h["number"], h["mine"], round(h["similarity"], 2)) for h in hits], [(1, True, 0.9), (2, False, 0.8), (6, False, 0.6)])
        numeros = {h["number"] for h in hits}
        self.assertTrue(numeros.isdisjoint({3, 4, 5}))        # close, abandonnée, sous le seuil
        self.assertTrue(numeros.isdisjoint(set(range(7, 11))))  # les expériences closes créées pour les cas
        self.assertEqual(hits[0]["notes_count"], 1)
        self.assertEqual(hits[1]["notes_count"], 0)
        self.assertEqual(set(hits[0]), {"number", "author", "mine", "started_on", "review_due", "posture", "problem", "context", "hypotheses",
                                        "chosen_path", "tested", "expected_signal", "success_criterion", "notes_count", "similarity", "score"})

    def test_mine_faux_partout_sans_auteur(self):
        hits = cs.search_experiments(self.reader, embed_constant(E1), QUESTION, None, limit=10)
        self.assertTrue(hits)
        self.assertFalse(any(h["mine"] for h in hits))

    def test_experience_close_ou_abandonnee_n_est_jamais_rendue(self):
        n = cs.start_experiment(self.writer, embed_par_marqueur, draft(problem="nouvelle [c99]"), ME, TODAY, names=NOMS)
        self.assertEqual(cs.search_experiments(self.reader, embed_constant(E1), QUESTION, ME)[0]["number"], n)
        cs.drop(self.writer, n, ME)
        self.assertNotIn(n, [h["number"] for h in cs.search_experiments(self.reader, embed_constant(E1), QUESTION, ME, limit=10)])

    def test_la_transaction_de_lecture_est_annulee(self):
        cs.search_cases(self.reader, embed_constant(E1), QUESTION)
        self.assertEqual(self.reader.info.transaction_status.name, "IDLE")
        cs.search_experiments(self.reader, embed_constant(E1), QUESTION, ME)
        self.assertEqual(self.reader.info.transaction_status.name, "IDLE")
        cs.due_reviews(self.reader, ME, TODAY)
        self.assertEqual(self.reader.info.transaction_status.name, "IDLE")

    def test_lecteur_paresseux_sur_la_base(self):
        reader = cs.CasesReader(connect=lambda: self.reader, embed=embed_constant(E1), today=TODAY, author=ME)
        self.assertEqual(reader.search_cases(QUESTION)[0]["number"], 1)
        self.assertEqual([h["number"] for h in reader.search_experiments(QUESTION)][:1], [1])
        # au 2027-03-01 injecté : l'expérience 5 (échéance par défaut = début + 6 semaines) est due, « proche » (2027-12-31) ne l'est pas
        dues = reader.list_due_reviews()
        self.assertEqual([(r["number"], r["review_due"]) for r in dues], [(5, "2027-02-15")])

    def test_un_jeu_d_essai_refuse_n_ecrit_rien(self):
        mauvais = self.dossier / "mauvais.yaml"
        mauvais.write_text("experiments:\n  - {author: agile-lead-test, started_on: 2027-01-04, problem: 'x [c50]'}\n", encoding="utf-8")
        with self.assertRaises(cs.CasesError):
            cs.load_fixture(self.super, embed_par_marqueur, mauvais)
        self.assertEqual(self.lire("SELECT count(*) FROM cases.experiments"), [(10,)])


class ChargementDuJeuDEssaiSansBase(AvecDossier):
    def charger(self, contenu):
        chemin = self.liste(contenu, "f.yaml")
        return cs.load_fixture(FausseConnexion([(1,)]), embed_par_marqueur, chemin)

    def test_cle_inconnue_ou_champ_manquant_refuse_avant_ecriture(self):
        conn = FausseConnexion()
        for contenu in ("autre: []\n", "experiments:\n  - {author: a, started_on: 2027-01-04, problem: 'p [c50]', couleur: bleu}\n",
                        "cases:\n  - {author: a, launched_on: 2026-06-01, reviewed_on: 2026-07-13, problem: 'p [c50]', tested: t, "
                        "context: {phase: x}, expected_signal: s, success_criterion: c}\n"):
            with self.subTest(contenu=contenu[:30]), self.assertRaises(cs.CasesError):
                cs.load_fixture(conn, embed_par_marqueur, self.liste(contenu, "f.yaml"))
        self.assertEqual((conn.executed, conn.commits), ([], 0))

    def test_ne_lit_pas_la_liste_des_noms_sensibles_et_accepte_les_dates_fixes(self):
        contenu = ("cases:\n  - {author: a, launched_on: 2020-06-01, reviewed_on: 2020-07-13, problem: 'p Quxlorian [c50]', tested: t, "
                   "context: {phase: x}, expected_signal: s, success_criterion: c, outcome: worked}\n")
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.dossier / "absente.txt")}):
            self.assertEqual(self.charger(contenu), {"experiments": 0, "cases": 1})


if __name__ == "__main__":
    unittest.main()
