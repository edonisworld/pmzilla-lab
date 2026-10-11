"""
Tests des sous-commandes `experiment` du journal (tools/journal_lab.py, db-lot2 groupe 6) sur un faux module des cas.

    uv run --with pyyaml python -m unittest discover -s tests/journal_lab -v

`journal.cases_store` et `journal.connect_cases` sont remplacés par des doublures : aucune base, aucun Ollama. La liste des noms
sensibles est un fichier inventé (PMZILLA_LAB_SENSITIVE_NAMES). L'auteur est un pseudonyme inventé. Données inventées uniquement.
"""
import contextlib
import datetime as dt
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_journal_lab as base  # noqa: E402

journal = base.journal
from cases_store import CasesError  # noqa: E402
from journal_lab_messages import CATALOGS  # noqa: E402

AUTEUR = "agile-lead-test"
BROUILLON = "problem: Les actions de rétro restent vagues.\ncontext:\n  team_type: équipe produit\nsuccess_criterion: Deux actions sur trois terminées.\n"


class Experiment(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.liste = self.tmp / "noms.txt"
        self.liste.write_text("nom-invente\n", encoding="utf-8")
        self.store = mock.MagicMock(name="cases_store")
        self.store.CasesError = CasesError
        self.store.resolve_author.return_value = AUTEUR
        self.store.start_experiment.side_effect = lambda conn, *a, **k: (conn() if callable(conn) else None, 7)[1]
        self.store.validate_start_draft.return_value = {"review_due": dt.date(2026, 11, 17)}
        self.store.validate_note_draft.return_value = {"note": "n", "noted_on": dt.date(2026, 10, 6)}
        self.store.add_note.return_value = None
        self.store.postpone.return_value = {"review_due": "2026-10-20", "postponements": 1}
        self.store.close_experiment.return_value = 4
        self.store.due_reviews.return_value = []
        self.store.show_experiment.return_value = {
            "number": 1, "author": AUTEUR, "status": "running", "started_on": "2026-10-01", "review_due": "2026-11-12",
            "postponements": 0, "posture": "none", "problem": "Problème inventé", "context": {"team_type": "équipe produit"},
            "hypotheses": ["H1"], "chosen_path": "Chemin", "references_used": [], "tested": "Un critère de fin",
            "expected_signal": "Signal", "success_criterion": "Critère",
            "notes": [{"noted_on": "2026-10-03", "note": "Première note"}]}
        self.connexion = mock.MagicMock(name="connexion")
        self.connect = mock.MagicMock(name="connect_cases", return_value=self.connexion)
        for patch in (mock.patch.object(journal, "cases_store", self.store), mock.patch.object(journal, "connect_cases", self.connect),
                      mock.patch.object(journal, "JOURNAL_DIR", self.tmp / "Journal-Lab"),
                      mock.patch.object(journal, "JOURNAL_FILE", self.tmp / "Journal-Lab" / "journal.yaml"),
                      mock.patch.object(journal, "WORKSPACE", self.tmp),
                      mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.liste)})):
            patch.start()
            self.addCleanup(patch.stop)

    def brouillon(self, texte=BROUILLON, nom="brouillon.yaml"):
        chemin = self.tmp / nom
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def run_cli(self, *arguments):
        """(code de sortie, stdout, stderr)."""
        sortie, erreur = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.object(sys, "argv", ["journal_lab.py", "--today", base.AUJOURDHUI, *arguments]), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            try:
                journal.main()
            except SystemExit as fin:
                code = fin.code if isinstance(fin.code, int) else (1 if fin.code else 0)
                if isinstance(fin.code, str):
                    erreur.write(fin.code + "\n")
        return code, sortie.getvalue(), erreur.getvalue()


class Ecritures(Experiment):
    def test_start_reussi_supprime_le_brouillon(self):
        chemin = self.brouillon()
        code, out, err = self.run_cli("experiment", "start", str(chemin))
        self.assertEqual(code, 0, err)
        self.assertIn("7", out)
        self.assertIn("2026-11-17", out)
        self.assertFalse(chemin.exists())
        self.store.start_experiment.assert_called_once()
        self.assertEqual(self.store.start_experiment.call_args.args[3], AUTEUR)
        self.connect.assert_called_once_with("pmzilla_cases")

    def test_start_refus_code_1_garde_le_brouillon(self):
        self.store.validate_start_draft.side_effect = CasesError("unknown key: zut", code="unknown_key", field="zut")
        chemin = self.brouillon()
        code, out, err = self.run_cli("experiment", "start", str(chemin))
        self.assertEqual(code, 1)
        self.assertIn("zut", out + err)
        self.assertTrue(chemin.exists())
        self.store.start_experiment.assert_not_called()
        self.connect.assert_not_called()

    def test_refus_de_la_couche_d_acces_code_1(self):
        self.store.start_experiment.side_effect = CasesError("field problem is longer", code="field_too_long", field="problem")
        chemin = self.brouillon()
        code, out, err = self.run_cli("experiment", "start", str(chemin))
        self.assertEqual(code, 1)
        self.assertIn("problem", err)
        self.assertTrue(chemin.exists())

    def test_embedding_indisponible_code_2(self):
        self.store.start_experiment.side_effect = CasesError("the embedding service must run", code="embedding_unavailable")
        chemin = self.brouillon()
        code, out, err = self.run_cli("experiment", "start", str(chemin))
        self.assertEqual(code, 2)
        self.assertIn("Ollama", err)
        self.assertTrue(chemin.exists())

    def test_base_injoignable_code_2(self):
        self.connect.side_effect = RuntimeError("mot de passe: secret-invente")
        chemin = self.brouillon()
        code, out, err = self.run_cli("experiment", "start", str(chemin))
        self.assertEqual(code, 2)
        self.assertNotIn("secret-invente", out + err)
        self.assertTrue(chemin.exists())

    def test_sans_auteur_code_2_et_nomme_le_fichier(self):
        self.store.resolve_author.return_value = None
        for arguments in (("start", self.brouillon()), ("note", 1, self.brouillon()), ("close", 1, self.brouillon()),
                          ("postpone", 1, "2w"), ("drop", 1), ("due",)):
            code, out, err = self.run_cli("experiment", *map(str, arguments))
            self.assertEqual(code, 2, arguments)
            self.assertIn(".pmzilla/cases.yaml", err)
        self.connect.assert_not_called()

    def test_note_et_close(self):
        chemin = self.brouillon("note: Une note.\n", "n.yaml")
        code, out, err = self.run_cli("experiment", "note", "1", str(chemin))
        self.assertEqual(code, 0, err)
        self.assertFalse(chemin.exists())
        self.store.add_note.assert_called_once()
        chemin = self.brouillon("outcome: worked\n", "c.yaml")
        code, out, err = self.run_cli("experiment", "close", "1", str(chemin))
        self.assertEqual(code, 0, err)
        self.assertIn("4", out)
        self.assertFalse(chemin.exists())

    def test_close_refuse_garde_le_brouillon(self):
        self.store.close_experiment.side_effect = CasesError("not running", code="not_running", field="1")
        chemin = self.brouillon("outcome: worked\n", "c.yaml")
        code, out, err = self.run_cli("experiment", "close", "1", str(chemin))
        self.assertEqual(code, 1)
        self.assertTrue(chemin.exists())

    def test_note_refusee_garde_le_brouillon(self):
        self.store.validate_note_draft.side_effect = CasesError("unknown key", code="unknown_key", field="x")
        chemin = self.brouillon("note: a\nx: 1\n", "n.yaml")
        code, out, err = self.run_cli("experiment", "note", "1", str(chemin))
        self.assertEqual(code, 1)
        self.assertTrue(chemin.exists())

    def test_postpone_et_drop(self):
        code, out, err = self.run_cli("experiment", "postpone", "1", "2w")
        self.assertEqual(code, 0, err)
        self.assertIn("2026-10-20", out)
        self.store.postpone.assert_called_once()
        self.assertEqual(self.store.postpone.call_args.args[1:3], (1, "2w"))
        code, out, err = self.run_cli("experiment", "drop", "1")
        self.assertEqual(code, 0, err)
        self.store.drop.assert_called_once()

    def test_troisieme_report_refuse_demande_close_ou_drop(self):
        self.store.postpone.side_effect = CasesError("limit", code="postponement_limit", field="1")
        code, out, err = self.run_cli("experiment", "postpone", "1", "1w")
        self.assertEqual(code, 1)
        self.assertIn("close", err)
        self.assertIn("drop", err)

    def test_sous_commandes_francaises_refusees(self):
        for arguments in (("bilan", "1"), ("reporter", "1", "2w")):
            code, out, err = self.run_cli("experiment", *arguments)
            self.assertEqual(code, 2, arguments)
            self.assertIn("invalid choice", err)
        self.connect.assert_not_called()
        self.store.postpone.assert_not_called()

    def test_messages_dans_les_deux_langues(self):
        _, francais, _ = self.run_cli("experiment", "drop", "1")
        _, anglais, _ = self.run_cli("experiment", "drop", "1", "--language", "en")
        self.assertNotEqual(francais, anglais)
        self.assertIn("abandonn", francais)
        self.assertIn("dropped", anglais)
        _, anglais, _ = self.run_cli("experiment", "start", str(self.brouillon()), "--language", "en")
        self.assertIn("review", anglais)


class BrouillonIllisible(Experiment):
    """Un brouillon absent ou qui n'est pas du YAML valide est refusé avec le code 1, sans rien écrire ni se connecter."""

    def verifie_rien_ecrit(self):
        self.store.start_experiment.assert_not_called()
        self.store.validate_start_draft.assert_not_called()
        self.connect.assert_not_called()

    def test_start_sur_un_fichier_absent_code_1(self):
        chemin = self.tmp / "absent.yaml"
        code, out, err = self.run_cli("experiment", "start", str(chemin))
        self.assertEqual(code, 1)
        self.assertIn("absent.yaml", err)
        self.assertFalse(chemin.exists())
        self.verifie_rien_ecrit()

    def test_start_sur_un_yaml_casse_code_1_et_garde_le_fichier(self):
        chemin = self.brouillon("problem: [non fermé\n  : : :\n", nom="casse.yaml")
        code, out, err = self.run_cli("experiment", "start", str(chemin))
        self.assertEqual(code, 1)
        self.assertIn("ParserError", err)   # le nom du type seulement, jamais le texte de l'erreur
        self.assertTrue(chemin.exists())
        self.verifie_rien_ecrit()


class ListeDesNoms(Experiment):
    def lancer_les_trois(self, *langue):
        resultats = []
        for arguments in (("start", self.brouillon(nom="s.yaml")), ("note", 1, self.brouillon("note: a\n", "n.yaml")),
                          ("close", 1, self.brouillon("outcome: worked\n", "c.yaml"))):
            resultats.append((arguments[-1], self.run_cli("experiment", *map(str, arguments), *langue)))
        return resultats

    def test_liste_sans_aucun_nom(self):
        self.liste.write_text("# commentaire\n\n", encoding="utf-8")
        for langue, extrait in ((("--language", "fr"), "aucun nom"), (("--language", "en"), "no name")):
            for chemin, (code, out, err) in self.lancer_les_trois(*langue):
                self.assertEqual(code, 2)
                self.assertIn(str(self.liste), err)
                self.assertIn(extrait, err)
                self.assertTrue(chemin.exists())
        self.connect.assert_not_called()
        self.store.start_experiment.assert_not_called()

    def test_liste_absente(self):
        self.liste.unlink()
        for langue in (("--language", "fr"), ("--language", "en")):
            for chemin, (code, out, err) in self.lancer_les_trois(*langue):
                self.assertEqual(code, 2)
                self.assertIn(str(self.liste), err)
                self.assertTrue(chemin.exists())
        self.connect.assert_not_called()
        francais = self.run_cli("experiment", "drop", "1")  # le message des deux cas diffère par la clé seule
        self.assertEqual(francais[0], 0)
        self.assertNotEqual(CATALOGS["fr"]["sensitive_names_missing"], CATALOGS["fr"]["sensitive_names_empty"])
        self.assertNotEqual(CATALOGS["en"]["sensitive_names_missing"], CATALOGS["en"]["sensitive_names_empty"])

    def test_postpone_et_drop_ne_lisent_pas_la_liste(self):
        for contenu in ("# rien\n", None):
            if contenu is None:
                self.liste.unlink()
            else:
                self.liste.write_text(contenu, encoding="utf-8")
            with mock.patch.object(journal.sensitive_names, "load_names", side_effect=AssertionError("liste lue")):
                self.assertEqual(self.run_cli("experiment", "postpone", "1", "2w")[0], 0)
                self.assertEqual(self.run_cli("experiment", "drop", "1")[0], 0)

    def test_les_lectures_ne_lisent_pas_la_liste(self):
        self.liste.unlink()
        with mock.patch.object(journal.sensitive_names, "load_names", side_effect=AssertionError("liste lue")):
            self.assertEqual(self.run_cli("experiment", "show", "1")[0], 0)
            self.assertEqual(self.run_cli("experiment", "due")[0], 0)


class Lectures(Experiment):
    def test_show(self):
        code, out, err = self.run_cli("experiment", "show", "1")
        self.assertEqual(code, 0, err)
        self.assertIn("Problème inventé", out)
        self.assertIn("Première note", out)
        self.assertIn("2026-11-12", out)
        self.connect.assert_called_once_with("pmzilla_cases_ro")

    def test_show_numero_inconnu(self):
        self.store.show_experiment.side_effect = CasesError("unknown experiment number 99", code="unknown_experiment", field="99")
        code, out, err = self.run_cli("experiment", "show", "99")
        self.assertEqual(code, 1)
        self.assertIn("99", err)

    def test_show_base_injoignable(self):
        self.connect.side_effect = RuntimeError("x")
        self.assertEqual(self.run_cli("experiment", "show", "1")[0], 2)

    def test_due(self):
        self.store.due_reviews.return_value = [
            {"number": 3, "problem": "Un problème inventé", "review_due": "2026-10-01", "postponements": 2, "decision_required": True}]
        code, out, err = self.run_cli("experiment", "due")
        self.assertEqual(code, 0, err)
        self.assertIn("3", out)
        self.assertIn("2026-10-01", out)
        self.assertIn("Un problème inventé", out)
        code, out, err = self.run_cli("experiment", "due", "--language", "en")
        self.assertIn("decision required", out)

    def test_due_sans_bilan_du(self):
        code, out, err = self.run_cli("experiment", "due")
        self.assertEqual(code, 0)
        self.assertTrue(out.strip())

    def test_due_base_injoignable_code_2(self):
        self.connect.side_effect = RuntimeError("x")
        self.assertEqual(self.run_cli("experiment", "due")[0], 2)


class SessionHook(Experiment):
    def test_sans_auteur_rien_et_aucune_connexion(self):
        self.store.resolve_author.return_value = None
        code, out, err = self.run_cli("experiment", "due", "--session-hook")
        self.assertEqual((code, out, err), (0, "", ""))
        self.connect.assert_not_called()

    def test_base_injoignable_une_ligne_code_0(self):
        self.connect.side_effect = RuntimeError("secret-invente")
        code, out, err = self.run_cli("experiment", "due", "--session-hook")
        self.assertEqual(code, 0)
        self.assertEqual(len((out + err).strip().splitlines()), 1)
        self.assertNotIn("secret-invente", out + err)
        self.assertEqual(self.connect.call_args.kwargs.get("timeout"), 2)

    def test_erreur_a_la_lecture_une_ligne_code_0(self):
        self.store.due_reviews.side_effect = CasesError("boom", code="database_refused")
        code, out, err = self.run_cli("experiment", "due", "--session-hook")
        self.assertEqual(code, 0)
        self.assertEqual(len((out + err).strip().splitlines()), 1)

    def test_sortie_demandee_par_la_base_ou_la_couche_d_acces_une_ligne_code_0(self):
        # SystemExit n'est pas une Exception : le crochet doit quand même sortir 0, sans trace
        for nom, installer in (
                ("connexion", lambda: setattr(self.connect, "side_effect", SystemExit("secret-invente"))),
                ("lecture", lambda: setattr(self.store.due_reviews, "side_effect", SystemExit(2))),
                ("auteur", lambda: setattr(self.store.resolve_author, "side_effect", SystemExit(1)))):
            with self.subTest(point=nom):
                self.connect.side_effect = None
                self.store.due_reviews.side_effect = None
                self.store.resolve_author.side_effect = None
                self.store.resolve_author.return_value = AUTEUR
                installer()
                code, out, err = self.run_cli("experiment", "due", "--session-hook")
                self.assertEqual(code, 0)
                self.assertLessEqual(len((out + err).strip().splitlines()), 1)
                self.assertNotIn("Traceback", out + err)
                self.assertNotIn("secret-invente", out + err)

    def test_base_refusee_hors_crochet_garde_le_code_1(self):
        self.store.due_reviews.side_effect = CasesError("boom", code="database_refused")
        self.assertEqual(self.run_cli("experiment", "due")[0], 1)

    def test_aucun_bilan_du_rien(self):
        code, out, err = self.run_cli("experiment", "due", "--session-hook")
        self.assertEqual((code, out, err), (0, "", ""))

    def test_bilans_dus_en_tete_lignes_et_consigne(self):
        self.store.due_reviews.return_value = [
            {"number": 3, "problem": "Premier problème inventé", "review_due": "2026-10-01", "postponements": 0, "decision_required": False},
            {"number": 5, "problem": "Second problème inventé", "review_due": "2026-10-04", "postponements": 2, "decision_required": True}]
        for langue, requis in ((None, "décision requise"), ("en", "decision required")):
            extra = ("--language", langue) if langue else ()
            code, out, err = self.run_cli("experiment", "due", "--session-hook", *extra)
            lignes = out.splitlines()
            self.assertEqual(code, 0)
            self.assertEqual(len(lignes), 4, out)
            self.assertIn("3", lignes[1])
            self.assertIn("2026-10-01", lignes[1])
            self.assertIn("Premier problème inventé", lignes[1])
            self.assertNotIn(requis, lignes[1])
            self.assertIn(requis, lignes[2])
            for mot in ("close", "postpone", "drop"):
                self.assertIn(mot, lignes[3])
        self.connect.assert_called_with("pmzilla_cases_ro", timeout=2)


class SuivisEtDeprecation(Experiment):
    def ajouter(self):
        self.assertEqual(self.run_cli("add", str(self.brouillon(base.ENTREE, "e.yaml")))[0], 0)

    def test_follow_ups_sans_auteur_inchange(self):
        self.ajouter()
        self.store.resolve_author.return_value = None
        self.connect.reset_mock()
        _, avec, _ = self.run_cli("follow-ups")
        self.assertNotIn("pmzilla_cases", avec)
        self.connect.assert_not_called()
        self.store.due_reviews.assert_not_called()

    def test_follow_ups_avec_auteur_bloc_des_bilans_dus_apres_les_experiences_yaml(self):
        self.ajouter()
        _, sans, _ = self.run_cli("follow-ups")
        self.store.due_reviews.return_value = [
            {"number": 3, "problem": "Un problème inventé", "review_due": "2026-10-01", "postponements": 0, "decision_required": False}]
        code, out, err = self.run_cli("follow-ups")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(sans.rstrip("\n")))
        reste = out[len(sans):]
        self.assertIn("Un problème inventé", reste)
        self.assertIn("2026-10-01", reste)

    def test_follow_ups_base_injoignable_une_ligne_meme_code(self):
        self.ajouter()
        _, sans, _ = self.run_cli("follow-ups")
        self.connect.side_effect = RuntimeError("secret-invente")
        code, out, err = self.run_cli("follow-ups")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(sans))
        self.assertEqual(len(out[len(sans):].strip().splitlines()), 1)
        self.assertNotIn("secret-invente", out + err)

    def test_follow_ups_aucun_bilan_du_sortie_identique(self):
        self.ajouter()
        _, avec, _ = self.run_cli("follow-ups")
        self.store.resolve_author.return_value = None
        _, sans, _ = self.run_cli("follow-ups")
        self.assertEqual(avec, sans)

    def test_deprecation_a_l_ajout(self):
        code, out, err = self.run_cli("add", str(self.brouillon(base.ENTREE, "e.yaml")))
        self.assertEqual(code, 0)
        self.assertIn("expérience J-20261001-1.x : bilan le 2026-10-04", out)
        self.assertEqual(err.count("experiment start"), 1)
        self.assertEqual(len(err.strip().splitlines()), 1)
        code, out, err = self.run_cli("add", str(self.brouillon("type: rétro\nperimetre: équipe Alpha\ntente: A.\nconstat: B.\n", "s.yaml")))
        self.assertEqual(err, "")

    def test_deprecation_en_anglais(self):
        _, _, err = self.run_cli("add", str(self.brouillon(base.ENTREE, "e.yaml")), "--language", "en")
        self.assertIn("deprecated", err)

    def test_deprecation_au_suivi_une_seule_fois(self):
        self.ajouter()
        code, out, err = self.run_cli("follow-ups")
        self.assertEqual(err.count("experiment start"), 1)
        self.assertIn("J-20261001-1.x", out)
        self.run_cli("update", "J-20261001-1.x", "conclue", "--note", "Fait.")
        code, out, err = self.run_cli("follow-ups")
        self.assertEqual(err, "")

    def test_deprecation_ne_change_pas_la_sortie_standard(self):
        # même entrée, même sortie qu'avant : ce que le journal historique affichait
        code, out, err = self.run_cli("add", str(self.brouillon(base.ENTREE, "e.yaml")))
        self.assertTrue(out.startswith("Séance notée : J-20261001-1 · rétro · équipe Alpha\n"))
        self.assertEqual(out.count("\n"), 4)


class Catalogues(unittest.TestCase):
    def test_cles_des_deux_langues(self):
        from messages import check_catalogs
        self.assertEqual(check_catalogs(CATALOGS), [])


class SessionHookProcessusReel(unittest.TestCase):
    """Le vrai script, dans un vrai processus, face à une base absente : une ligne au plus, code 0, jamais de trace."""

    def test_base_absente_ou_refusee(self):
        racine = Path(__file__).resolve().parents[2]
        env = dict(os.environ, PMZILLA_LAB_CASES_AUTHOR=AUTEUR, PMZILLA_LAB_CASES_DBNAME="pmzilla_eval_absent",
                   PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES_RO="mot-de-passe-invente")
        import subprocess
        fait = subprocess.run([sys.executable, "-W", "ignore", str(racine / "tools" / "journal_lab.py"), "experiment", "due", "--session-hook"],
                              capture_output=True, text=True, env=env, cwd=str(racine), timeout=60)
        self.assertEqual(fait.returncode, 0, fait.stderr)
        self.assertLessEqual(len((fait.stdout + fait.stderr).strip().splitlines()), 1, fait.stdout + fait.stderr)
        self.assertNotIn("Traceback", fait.stdout + fait.stderr)
        self.assertNotIn("mot-de-passe-invente", fait.stdout + fait.stderr)


class SessionHookSeanceEvaluation(unittest.TestCase):
    """Branche A de la sonde : le crochet tourne dans les séances d'évaluation ; il doit y rester silencieux et sortir 0."""

    def test_sans_base_jetable_auteur_vide_rien_et_code_0(self):
        racine = Path(__file__).resolve().parents[2]
        import subprocess
        with tempfile.TemporaryDirectory() as espace:     # espace de travail vide : pas de .pmzilla/cases.yaml
            env = dict(os.environ, PMZILLA_LAB_CASES_AUTHOR="", PMZILLA_LAB_CASES_DBNAME="pmzilla_eval_absent",
                       PMZILLA_LAB_WORKSPACE=espace)
            fait = subprocess.run([sys.executable, "-W", "ignore", str(racine / "tools" / "journal_lab.py"), "experiment", "due", "--session-hook"],
                                  capture_output=True, text=True, env=env, cwd=str(racine), timeout=60)
        self.assertEqual((fait.returncode, fait.stdout, fait.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
