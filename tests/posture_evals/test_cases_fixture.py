"""
Jeu d'essai et base de cas jetable (db-lot2, groupe 12, design.md 7.1 et 7.2) : `cases_fixture`, environnement des séances,
base jetable (création, vidage, chargement, suppression), exclusion de .pmzilla/cases.yaml de la copie.

    bash tests/run_all.sh posture_evals

Aucun appel payant, aucune base réelle : `subprocess.run`, la création de la base, le vidage, le chargement et la suppression
sont remplacés par des faux ; `claude` n'est jamais lancé. Données inventées : auteur `agile-lead-test`, fichiers de jeu d'essai
écrits dans un dossier temporaire.
Non écrit ici (dépend de la sonde du groupe 0, tâche 12.1, dernière phrase) : « branche A seulement : l'environnement donné à la
commande de séance est celui qui porte les deux variables ».
"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import posture_evals as essai  # noqa: E402
import cases_store  # noqa: E402
import test_posture_evals as base  # noqa: E402

CREER_REELLE = essai.create_cases_database      # la classe de base de test_posture_evals la remplace par un faux
BASE_JETABLE = "pmzilla_eval_0a1b2c3d"
FIXTURE = "tests/postures/cases/un-cas.yaml"
FIXTURE_EN = "tests/postures/cases/un-cas.en.yaml"


class FausseConnexion:
    def __init__(self):
        self.executed, self.commits, self.closed = [], 0, False

    def execute(self, sql, params=None):
        self.executed.append(" ".join(sql.split()))

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class AvecFixtures(base.Base):
    def setUp(self):
        super().setUp()
        self.workspace = self.tmp / "workspace"
        (self.workspace / "tests" / "postures" / "cases").mkdir(parents=True)
        for name in ("un-cas.yaml", "un-cas.en.yaml"):
            (self.workspace / "tests" / "postures" / "cases" / name).write_text("experiments: []\n", encoding="utf-8")
        (self.tmp / "hors.yaml").write_text("experiments: []\n", encoding="utf-8")


class FixtureDansUnCas(AvecFixtures):
    CAS = {"id": "c1", "question": "Q ?", "cases_fixture": FIXTURE, "en": {"question": "Q en ?", "cases_fixture": FIXTURE_EN}}

    def test_le_bloc_en_remplace_la_fixture_et_le_cas_n_est_pas_modifie(self):
        original = json.dumps(self.CAS)
        self.assertEqual(essai.case_for_language(self.CAS, "fr")["cases_fixture"], FIXTURE)
        self.assertEqual(essai.case_for_language(self.CAS, "en")["cases_fixture"], FIXTURE_EN)
        self.assertEqual(json.dumps(self.CAS), original)

    def test_un_bloc_en_sans_fixture_garde_celle_du_cas(self):
        cas = {**self.CAS, "en": {"question": "Q en ?"}}
        self.assertEqual(essai.case_for_language(cas, "en")["cases_fixture"], FIXTURE)

    def test_chemins_acceptes(self):
        essai.check_fixtures([self.CAS, {"id": "c2", "question": "Q"}])      # ne lève rien

    def test_chemins_refuses_avec_le_nom_du_cas(self):
        for chemin in ("tests/postures/cases/absent.yaml", "../hors.yaml", "tests/postures/cases/../../../../hors.yaml",
                       str(self.tmp / "hors.yaml"), "tests/postures/cas.yaml", "tests/postures/cases"):
            for cas in ({"id": "cas-un", "cases_fixture": chemin}, {"id": "cas-un", "en": {"cases_fixture": chemin}}):
                with self.subTest(chemin=chemin, cas=list(cas)), self.assertRaises(SystemExit) as erreur:
                    essai.check_fixtures([cas])
                self.assertIn("cas-un", str(erreur.exception))

    def test_main_refuse_le_fichier_de_cas_avant_toute_base_ou_seance(self):
        essai.CASES_FILE.write_text(yaml.safe_dump([{"id": "cas-un", "question": "Q", "cases_fixture": "../hors.yaml"}]), encoding="utf-8")
        creer = mock.Mock()
        with mock.patch.object(essai, "create_cases_database", creer), mock.patch.object(sys, "argv", ["posture_evals.py"]), \
                self.assertRaises(SystemExit) as erreur:
            essai.main()
        self.assertIn("cas-un", str(erreur.exception))
        creer.assert_not_called()


class EnvironnementDesSeances(AvecFixtures):
    def test_variables_de_la_base_jetable_et_de_l_auteur_invente(self):
        self.assertEqual(essai.cases_environment(BASE_JETABLE),
                         {"PMZILLA_LAB_CASES_DBNAME": BASE_JETABLE, "PMZILLA_LAB_CASES_AUTHOR": "agile-lead-test"})
        self.assertEqual(essai.CASES_EVAL_AUTHOR, "agile-lead-test")

    def test_sans_base_nom_reserve_et_auteur_vide(self):
        self.assertEqual(essai.cases_environment(None),
                         {"PMZILLA_LAB_CASES_DBNAME": "pmzilla_eval_absent", "PMZILLA_LAB_CASES_AUTHOR": ""})

    def test_les_noms_de_variables_sont_ceux_du_module_des_cas(self):
        self.assertEqual(set(essai.cases_environment(None)), {cases_store.DBNAME_VARIABLE, cases_store.AUTHOR_VARIABLE})

    def test_configuration_mcp_porte_les_deux_variables(self):
        env = essai.cases_environment(BASE_JETABLE)
        for base_bibliotheque in (None, "pmzilla_eval_bibliotheque"):
            config = json.loads(essai.mcp_config(self.tmp, base_bibliotheque, cases_env=env, label=base_bibliotheque).read_text())
            serveur = config["mcpServers"]["pmzilla-library"]
            self.assertEqual({k: serveur["env"][k] for k in env}, env)
            self.assertNotIn("PMZILLA_LAB_DATA", serveur["env"])
            if base_bibliotheque:
                self.assertEqual(serveur["env"]["PMZILLA_LAB_KNOWLEDGE_DBNAME"], base_bibliotheque)

    def test_configuration_mcp_sans_cases_env_est_inchangee(self):
        serveur = json.loads(essai.mcp_config(self.tmp).read_text())["mcpServers"]["pmzilla-library"]
        self.assertNotIn("env", serveur)

    def test_la_commande_de_seance_recoit_l_environnement(self):
        vus = []

        def faux_run(commande, **options):
            vus.append(options.get("env"))
            return self.termine("")

        env = essai.cases_environment(BASE_JETABLE)
        with mock.patch.object(essai.subprocess, "run", faux_run):
            essai.run_session("Q ?", self.tmp, self.tmp / "mcp.json", None, self.tmp / "t.jsonl", False, env=env)
        self.assertEqual({k: vus[0][k] for k in env}, env)
        self.assertIn("PATH", vus[0])             # l'environnement courant est conservé

    def test_la_seance_prend_la_copie_pour_espace_de_travail(self):
        # le crochet de début de séance lit l'auteur dans l'espace de travail : jamais le .pmzilla/cases.yaml du vrai dépôt
        vus = []

        def faux_run(commande, **options):
            vus.append(options.get("env"))
            return self.termine("")

        for env in (essai.cases_environment(BASE_JETABLE), essai.cases_environment(None), None):
            with self.subTest(env=env), mock.patch.object(essai.subprocess, "run", faux_run):
                essai.run_session("Q ?", self.tmp, self.tmp / "mcp.json", None, self.tmp / "t.jsonl", False, env=env)
                self.assertEqual(vus[-1]["PMZILLA_LAB_WORKSPACE"], str(self.tmp))

    def test_12_1b_la_seance_porte_les_deux_variables_que_le_crochet_herite(self):
        # branche A de la sonde : le crochet SessionStart tourne dans la séance, avec l'environnement de la séance
        for avec_base, auteur, base_attendue in ((BASE_JETABLE, "agile-lead-test", BASE_JETABLE), (None, "", "pmzilla_eval_absent")):
            with self.subTest(base=avec_base):
                env = essai.cases_environment(avec_base)
                self.assertEqual(env[cases_store.AUTHOR_VARIABLE], auteur)
                self.assertEqual(env[cases_store.DBNAME_VARIABLE], base_attendue)


class MessageDeBaseIndisponible(unittest.TestCase):
    """Base jetable impossible à créer : le message de l'erreur de connexion (déjà sans secret) est affiché, pas seulement son type."""

    def test_le_message_nomme_la_variable_manquante_jamais_une_valeur(self):
        import db
        erreur = db.ErreurBase("Connexion à la base impossible : refusée. Aucun mot de passe trouvé (Trousseau pmzilla-lab-db, "
                               "puis PMZILLA_LAB_DB_PASSWORD).")
        sortie = io.StringIO()
        with mock.patch.object(db, "connect", side_effect=erreur), mock.patch.object(essai, "library_backend", lambda: "postgres"), \
                contextlib.redirect_stderr(sortie):
            self.assertIsNone(essai.create_cases_database())
        self.assertIn("PMZILLA_LAB_DB_PASSWORD", sortie.getvalue())
        self.assertIn("Base de cas jetable indisponible", sortie.getvalue())

    def test_une_autre_exception_n_affiche_que_son_type(self):
        import db
        sortie = io.StringIO()
        with mock.patch.object(db, "connect", side_effect=RuntimeError("secret-invente")), \
                mock.patch.object(essai, "library_backend", lambda: "postgres"), contextlib.redirect_stderr(sortie):
            self.assertIsNone(essai.create_cases_database())
        self.assertIn("RuntimeError", sortie.getvalue())
        self.assertNotIn("secret-invente", sortie.getvalue())


class BaseJetable(AvecFixtures):
    def test_vidage_puis_chargement_de_la_fixture(self):
        conn = FausseConnexion()
        charge = mock.Mock(return_value={"experiments": 0, "cases": 0})
        with mock.patch.object(essai, "connect_cases_database", return_value=conn) as connexion, \
                mock.patch.object(cases_store, "load_fixture", charge):
            essai.reset_cases_database(BASE_JETABLE, self.workspace / FIXTURE)
        connexion.assert_called_once_with(BASE_JETABLE)
        self.assertEqual(conn.executed, ["TRUNCATE cases.cases, cases.experiment_notes, cases.experiments RESTART IDENTITY"])
        self.assertGreaterEqual(conn.commits, 1)
        self.assertEqual(charge.call_args.args[0], conn)
        self.assertEqual(Path(charge.call_args.args[2]), self.workspace / FIXTURE)
        self.assertTrue(conn.closed)

    def test_sans_fixture_seulement_le_vidage(self):
        conn = FausseConnexion()
        charge = mock.Mock()
        with mock.patch.object(essai, "connect_cases_database", return_value=conn), mock.patch.object(cases_store, "load_fixture", charge):
            essai.reset_cases_database(BASE_JETABLE, None)
        self.assertEqual(len(conn.executed), 1)
        charge.assert_not_called()
        self.assertTrue(conn.closed)

    def test_fixture_refusee_ferme_quand_meme_la_connexion(self):
        conn = FausseConnexion()
        with mock.patch.object(essai, "connect_cases_database", return_value=conn), \
                mock.patch.object(cases_store, "load_fixture", side_effect=cases_store.CasesError("non")), \
                self.assertRaises(cases_store.CasesError):
            essai.reset_cases_database(BASE_JETABLE, self.workspace / FIXTURE)
        self.assertTrue(conn.closed)

    def test_voie_sqlite_ou_base_en_panne_pas_de_base_jetable(self):
        import db
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("panne")) as connexion:
            self.assertIsNone(CREER_REELLE())
            connexion.assert_called()
        with mock.patch.dict(essai.os.environ, {"PMZILLA_LAB_BACKEND": "sqlite"}), \
                mock.patch.object(db, "connect", side_effect=AssertionError("aucune connexion")):
            self.assertIsNone(CREER_REELLE())

    def test_creation_migre_et_la_suppression_est_forcee(self):
        import db
        admin, migree = FausseConnexion(), FausseConnexion()
        connexions = [admin, migree]
        with mock.patch.dict(essai.os.environ, {}, clear=False), \
                mock.patch.object(db, "connect", side_effect=lambda *a, **k: connexions.pop(0)) as connexion, \
                mock.patch.object(db, "lister_migrations", return_value=["m"]), \
                mock.patch.object(db, "migrer") as migrer:
            essai.os.environ.pop("PMZILLA_LAB_BACKEND", None)
            nom = CREER_REELLE()
        self.assertRegex(nom, r"^pmzilla_eval_[0-9a-f]{12}$")
        self.assertTrue(admin.executed[0].startswith(f'CREATE DATABASE "{nom}"'))
        migrer.assert_called_once()
        self.assertEqual(connexion.call_args_list[1].kwargs.get("dbname"), nom)
        admin2 = FausseConnexion()
        with mock.patch.object(db, "connect", return_value=admin2):
            essai.drop_cases_database(nom)
        self.assertEqual(admin2.executed, [f'DROP DATABASE IF EXISTS "{nom}" WITH (FORCE)'])
        self.assertTrue(admin2.closed)


class PassageAvecBaseJetable(AvecFixtures):
    """main() avec une base jetable factice : ce que voient la séance, la configuration MCP, le vidage et la suppression."""

    CAS = [{"id": "avec", "question": "Question avec ?", "posture": "Delivery", "cases_fixture": FIXTURE},
           {"id": "sans", "question": "Question sans ?", "posture": "Delivery"}]

    def setUp(self):
        super().setUp()
        self.sessions, self.resets, self.drops, self.configs = [], [], [], []
        essai.CASES_FILE.write_text(yaml.safe_dump(self.CAS), encoding="utf-8")

        def seance(question, copie, mcp, model, trace, bash, language="fr", env=None):
            self.sessions.append((question, mcp, env))
            return [base.assistant(base.texte("[Posture : Delivery] réponse")), base.fin("[Posture : Delivery] réponse")]

        vrai_mcp = essai.mcp_config
        for patch in (mock.patch.object(essai, "git", lambda *a, **k: ""),
                      mock.patch.object(essai, "make_copy", lambda *a, **k: None),
                      mock.patch.object(essai, "prepare_memory", lambda *a, **k: {}),
                      mock.patch.object(essai, "drop_copy"),
                      mock.patch.object(essai, "run_session", seance),
                      mock.patch.object(essai, "reset_cases_database", lambda name, fixture: self.resets.append((name, fixture))),
                      mock.patch.object(essai, "drop_cases_database", lambda name: self.drops.append(name))):
            patch.start()
            self.addCleanup(patch.stop)
        self.vrai_mcp = vrai_mcp

    def lancer(self, *arguments, base_jetable=BASE_JETABLE, tolere_sortie=False):
        """Sortie standard du passage ; avec `tolere_sortie`, un SystemExit de fin de passage est rangé dans self.code."""
        sortie = io.StringIO()
        self.code = 0
        with mock.patch.object(essai, "create_cases_database", lambda: base_jetable), \
                mock.patch.object(sys, "argv", ["posture_evals.py", *arguments]), contextlib.redirect_stdout(sortie):
            if tolere_sortie:
                try:
                    essai.main()
                except SystemExit as fin:
                    self.code = fin.code
            else:
                essai.main()
        return sortie.getvalue()

    def resultats(self):
        return {c["id"]: c for c in json.loads(max(essai.DATA.glob("*/resultats.json")).read_text(encoding="utf-8"))["cas"]}

    def test_vidage_avant_chaque_cas_chargement_de_la_fixture_et_suppression_finale(self):
        self.lancer("--retries", "0")
        self.assertEqual(self.resets, [(BASE_JETABLE, self.workspace / FIXTURE), (BASE_JETABLE, None)])
        self.assertEqual(self.drops, [BASE_JETABLE])
        for _, mcp, env in self.sessions:
            self.assertEqual(env, essai.cases_environment(BASE_JETABLE))
            serveur = json.loads(Path(mcp).read_text())["mcpServers"]["pmzilla-library"]
            self.assertEqual(serveur["env"]["PMZILLA_LAB_CASES_DBNAME"], BASE_JETABLE)
            self.assertEqual(serveur["env"]["PMZILLA_LAB_CASES_AUTHOR"], "agile-lead-test")

    def test_un_rejeu_vide_et_recharge_encore(self):
        appels = []

        def seance(question, copie, mcp, model, trace, bash, language="fr", env=None):
            appels.append(question)
            tag = "Delivery" if len(appels) > 1 else "Discovery"      # la première séance échoue, le rejeu réussit
            return [base.assistant(base.texte(f"[Posture : {tag}] r")), base.fin(f"[Posture : {tag}] r")]

        with mock.patch.object(essai, "run_session", seance):
            self.lancer("--retries", "1", "--cases", "avec")
        self.assertEqual(len(self.resets), 2)

    def test_la_base_est_supprimee_meme_si_le_passage_plante(self):
        with mock.patch.object(essai, "write_report", side_effect=RuntimeError("panne")), self.assertRaises(RuntimeError):
            self.lancer("--retries", "0")
        self.assertEqual(self.drops, [BASE_JETABLE])

    def test_la_base_est_supprimee_si_le_verrou_est_pris(self):
        with mock.patch.object(essai, "lock_pass", side_effect=SystemExit("verrou")), self.assertRaises(SystemExit):
            self.lancer("--retries", "0")
        self.assertEqual(self.drops, [BASE_JETABLE])

    def test_base_indisponible_cas_a_fixture_non_evaluable_et_les_autres_sans_cas_ni_auteur(self):
        sortie = self.lancer("--retries", "0", base_jetable=None, tolere_sortie=True)
        resultats = self.resultats()
        self.assertEqual(resultats["avec"]["non_evaluable"], ["cases database unavailable"])
        self.assertIn("non évaluable ici : cases database unavailable", sortie)
        self.assertEqual(len(self.sessions), 1)
        _, mcp, env = self.sessions[0]
        self.assertEqual(env, {"PMZILLA_LAB_CASES_DBNAME": "pmzilla_eval_absent", "PMZILLA_LAB_CASES_AUTHOR": ""})
        serveur = json.loads(Path(mcp).read_text())["mcpServers"]["pmzilla-library"]
        self.assertEqual(serveur["env"], env)
        self.assertEqual((self.resets, self.drops), ([], []))

    def test_cas_non_evaluables_bilan_sur_le_total_attendu_et_passage_non_validant(self):
        sortie = self.lancer("--retries", "0", base_jetable=None, tolere_sortie=True)
        resultats = self.resultats()
        self.assertEqual(resultats["avec"]["bloquantes_attendues"], 1)           # sa seule vérification bloquante (la posture)
        self.assertEqual(self.code, essai.EXIT_NOT_VALIDATING)
        self.assertNotEqual(self.code, 0)
        self.assertIn("BILAN 1/2 · 1 non évaluable(s)", sortie)
        self.assertIn("passage non validant", sortie)
        donnees = json.loads(max(essai.DATA.glob("*/resultats.json")).read_text(encoding="utf-8"))
        self.assertIs(donnees["validant"], False)
        self.assertEqual(donnees["non_evaluables"], ["avec"])
        # le rapport est dans le dossier des rapports du passage (essai-<horodatage>.md), pas dans celui des traces
        rapports = list(essai.REPORT_DIR.glob("essai-*.md"))
        self.assertEqual(len(rapports), 1)
        rapport = rapports[0].read_text(encoding="utf-8")
        self.assertIn("1/2 vérifications réussies sur 2 cas, dont 1 non évaluable(s)", rapport)        # total sur les vérifications attendues
        avis = next(ligne for ligne in rapport.splitlines() if ligne.startswith("**Passage non validant**"))
        self.assertIn("1 cas non évaluable(s) (avec)", avis)                                           # l'avis nomme le cas
        self.assertNotIn("sans", avis)
        section = rapport[rapport.index("## avec"):rapport.index("## sans")]
        self.assertIn("Non évaluable", section)
        self.assertIn("- cases database unavailable", section)                                         # la raison, à la place des vérifications
        self.assertNotIn("✅", section)
        self.assertNotIn("❌", section)

    def test_sans_cas_non_evaluable_le_passage_reste_validant_et_sort_0(self):
        sortie = self.lancer("--retries", "0", tolere_sortie=True)
        self.assertEqual(self.code, 0)
        self.assertNotIn("non évaluable(s)", sortie)
        donnees = json.loads(max(essai.DATA.glob("*/resultats.json")).read_text(encoding="utf-8"))
        self.assertIs(donnees["validant"], True)

    def test_blocking_count_des_cas_livres_vaut_38(self):
        cas = yaml.safe_load((Path(essai.__file__).resolve().parents[1] / "tests" / "postures" / "cas.yaml").read_text(encoding="utf-8"))
        self.assertEqual(sum(essai.blocking_count(c) for c in cas), 38)

    def test_rejuger_ne_cree_aucune_base(self):
        passage = essai.DATA / "2026-10-01-090000"
        passage.mkdir(parents=True)
        (passage / "avec.jsonl").write_text("\n".join(json.dumps(e) for e in base.SEANCE), encoding="utf-8")
        (passage / "resultats.json").write_text(json.dumps({"base": "b", "memoire": "figée", "cas": []}), encoding="utf-8")
        creer = mock.Mock(return_value=BASE_JETABLE)
        sortie = io.StringIO()
        with mock.patch.object(essai, "create_cases_database", creer), \
                mock.patch.object(sys, "argv", ["posture_evals.py", "--rejudge", passage.name, "--cases", "avec"]), \
                contextlib.redirect_stdout(sortie):
            essai.main()
        creer.assert_not_called()
        self.assertEqual((self.sessions, self.resets, self.drops), ([], [], []))


class CopieSansFichierAuteur(AvecFixtures):
    def faux_git(self, *args, **kwargs):
        if args[:2] == ("worktree", "add"):
            copie = Path(args[3])
            (copie / ".pmzilla").mkdir(parents=True)
            (copie / ".pmzilla" / "cases.yaml").write_text("author: suivi-par-erreur\n", encoding="utf-8")   # même suivi par Git
            return ""
        if args and args[0] == "ls-files":
            return ".pmzilla/cases.yaml\0autre.txt\0"
        return ""

    def test_la_copie_ne_contient_jamais_le_fichier_local_de_l_auteur(self):
        (self.workspace / ".pmzilla").mkdir()
        (self.workspace / ".pmzilla" / "cases.yaml").write_text("author: auteur-invente\n", encoding="utf-8")
        (self.workspace / "autre.txt").write_text("x", encoding="utf-8")
        for reel in (True, False):
            copie = self.tmp / f"copie-{reel}"
            with mock.patch.object(essai, "git", self.faux_git):
                essai.make_copy(copie, "HEAD")
            with mock.patch.object(essai, "build_sanctums"), mock.patch.object(essai, "freeze_memory", return_value={}):
                (self.workspace / "tests" / "postures").mkdir(parents=True, exist_ok=True)
                (self.workspace / essai.CONTEXTE_NEUTRE).write_text("neutre", encoding="utf-8")
                (self.workspace / essai.CONTEXTE_LOCAL).parent.mkdir(exist_ok=True)
                (self.workspace / essai.CONTEXTE_LOCAL).write_text("local", encoding="utf-8")
                essai.prepare_memory(copie, reel)
            with self.subTest(memoire_reelle=reel):
                self.assertFalse((copie / ".pmzilla" / "cases.yaml").exists())
                self.assertTrue((copie / "autre.txt").exists())          # le reste est copié comme avant


class OutilsDesCas(unittest.TestCase):
    def test_search_cases_et_search_experiments_sont_reconnus(self):
        for outil in ("search_cases", "search_experiments", "list_due_reviews"):
            trace = essai.read_trace([base.assistant(base.appel(f"mcp__pmzilla-library__{outil}", {"query": "x"}, "t1")), base.fin("ok")])
            with self.subTest(outil=outil):
                self.assertTrue(essai.check_auto({"tool": outil}, trace, {})["ok"])
        trace = essai.read_trace([base.assistant(base.appel("mcp__pmzilla-library__search_library", {"query": "x"}, "t1")), base.fin("ok")])
        self.assertFalse(essai.check_auto({"tool": "search_cases"}, trace, {})["ok"])


if __name__ == "__main__":
    unittest.main()
