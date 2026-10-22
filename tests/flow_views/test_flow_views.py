"""
Tests de tools/flow_views.py : seule porte de Claude Code vers les données Jira de la base.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Tickets et équipes inventés. Les tests avec base utilisent une base jetable (sautés si elle manque) : la connexion sous le rôle
pmzilla_flow_views est simulée par SET ROLE, le mot de passe réel du rôle n'est jamais utilisé.
"""
import contextlib
import io
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "db"))
import db  # noqa: E402
import flow_views as fv  # noqa: E402
from flow_views_messages import CATALOGS  # noqa: E402
from messages import Messages, check_catalogs  # noqa: E402

T = Messages(CATALOGS, "fr")
CONNECT_REEL = db.connect
import test_db as base  # noqa: E402  (base jetable partagée avec les tests de db.py ; une erreur d'import fait échouer la suite)

# Suite hermétique (revue du 2026-10-21) : fv.main() lit le seuil de flux.yaml sous la racine de contenu ; sans ce réglage, il lirait le
# vrai Flux-Lab/flux.yaml, ou sortirait en 78 dans un arbre sans dépôt Git. Pour toute la suite, PMZILLA_LAB_WORKSPACE désigne un dossier
# temporaire sans flux.yaml (seuil au plancher de 5) ; un test qui pose sa propre racine la remplace le temps de son bloc.
_CONTENU_VIDE = None
_ENVIRONNEMENT = None


def setUpModule():
    global _CONTENU_VIDE, _ENVIRONNEMENT
    _CONTENU_VIDE = tempfile.TemporaryDirectory()
    _ENVIRONNEMENT = mock.patch.dict("os.environ", {"PMZILLA_LAB_WORKSPACE": _CONTENU_VIDE.name})
    _ENVIRONNEMENT.start()


def tearDownModule():
    _ENVIRONNEMENT.stop()
    _CONTENU_VIDE.cleanup()


class SansBase(unittest.TestCase):
    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_seuil_jamais_sous_cinq(self):
        self.assertEqual(fv.seuil_effectif(5, None), 5)
        self.assertEqual(fv.seuil_effectif(5, 2), 5)
        self.assertEqual(fv.seuil_effectif(8, 6), 8)
        self.assertEqual(fv.seuil_effectif(5, 12), 12)
        self.assertEqual(fv.seuil_effectif(1, 0), 5)

    def test_reglage_du_fichier(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "flux.yaml"
            self.assertEqual(fv.seuil_configure(T, f), 5)                  # absent
            f.write_text("flow_views_min_cell: 8\n", encoding="utf-8")
            self.assertEqual(fv.seuil_configure(T, f), 8)
            f.write_text("flow_views_min_cell: 2\n", encoding="utf-8")
            self.assertEqual(fv.seuil_configure(T, f), 5)                  # jamais en dessous de 5
            f.write_text("flow_views_min_cell: beaucoup\n", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(fv.seuil_configure(T, f), 5)

    def test_reglage_lu_sous_la_racine_de_contenu(self):
        # Décision du 2026-10-21, point 6 : depuis un worktree, flux.yaml est celui de la racine de contenu (tools/lab_paths.py), jamais
        # celui de la racine du code ; sinon le fichier est introuvable et le seuil retombe au plancher de 5 (on masque moins que prévu).
        with tempfile.TemporaryDirectory() as d:
            contenu = Path(d) / "contenu"
            (contenu / "Flux-Lab").mkdir(parents=True)
            (contenu / "Flux-Lab" / "flux.yaml").write_text("flow_views_min_cell: 9\n", encoding="utf-8")
            with mock.patch.dict("os.environ", {"PMZILLA_LAB_WORKSPACE": str(contenu)}):
                self.assertEqual(fv.fichier_config(), contenu.resolve() / "Flux-Lab" / "flux.yaml")
                self.assertNotEqual(fv.fichier_config().parent.parent, RACINE)
                self.assertEqual(fv.seuil_configure(T), 9)

    def test_suite_hermetique_sans_vrai_flux_yaml(self):
        # revue du 2026-10-21 : sans réglage propre au test, le fichier lu est sous le dossier temporaire de la suite, jamais le vrai
        self.assertEqual(fv.fichier_config().parent.parent, Path(_CONTENU_VIDE.name).resolve())
        self.assertFalse(fv.fichier_config().exists())
        self.assertEqual(fv.seuil_configure(T), 5)

    def test_racine_de_contenu_absente_refus_plutot_que_plancher(self):
        # PMZILLA_LAB_WORKSPACE sur un dossier absent : code 78 du module partagé, jamais un repli silencieux sur le plancher.
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict("os.environ", {"PMZILLA_LAB_WORKSPACE": str(Path(d) / "absent")}), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as fin:
                fv.seuil_configure(T)
            self.assertEqual(fin.exception.code, 78)

    def test_masquage_et_rendu(self):
        self.assertEqual(fv.masquer(None, 5, T), "masqué")                # idée #417 : le mot, jamais « <5 »
        self.assertEqual(fv.masquer(7, 10, T), "masqué")
        self.assertEqual(fv.masquer(12, 10, T), "12")
        texte = fv.rendre(["team", "tickets"], [("Alpha", 12), ("Beta", None), ("Gamma", 7)], 10, T)
        self.assertIn("Alpha  12", texte)
        self.assertIn("Beta   masqué", texte)
        self.assertIn("Gamma  masqué", texte)
        self.assertNotIn("<", texte)
        self.assertEqual(fv.rendre(["team", "tickets"], [], 5, T), "(aucune ligne)")

    def test_vue_inconnue_refusee_avant_toute_connexion(self):
        for nom in ("flow.issues", "v_team_status; DROP TABLE x", "issues", ""):
            with self.assertRaises(ValueError):
                fv.lire(nom)
        with mock.patch.object(db, "connect", side_effect=AssertionError("pas de connexion")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(fv.main(["show", "issues"]), 1)
            self.assertIn("Vue inconnue", err.getvalue())

    def test_connexion_sous_le_seul_role_des_vues(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("injoignable")) as connexion:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(fv.main(["show", "v_team_status"]), 1)
            connexion.assert_called_once_with(role="pmzilla_flow_views")
            self.assertIn("injoignable", err.getvalue())

    def test_liste_des_vues(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(fv.main(["list"]), 0)
        for vue in fv.VUES:
            self.assertIn(vue, sortie.getvalue())

    def test_les_quatre_vues_sont_celles_de_la_migration(self):
        texte = (RACINE / "db" / "migrations" / "0002_flow_schema.sql").read_text(encoding="utf-8")
        self.assertEqual(len(fv.VUES_FLOW), 4)
        for vue in fv.VUES_FLOW:
            self.assertIn(f"CREATE VIEW flow.{vue} ", texte)


QUALITE = ("quality_by_team", "quality_coverage_by_team", "quality_by_product")
EQUIPES = ("v_teams", "v_team_jira_ids")


class VuesDeQualite(unittest.TestCase):
    """R-78 (spec jira-flow-views) : les trois vues du schéma quality rejoignent la liste fermée, lues sous le rôle des vues de qualité."""

    def test_neuf_vues_connues_dont_les_trois_de_qualite_et_les_deux_des_noms_d_equipe(self):
        """Étendu par le change team-names-readable (tâche 2.4) : la liste fermée passe de sept à neuf vues."""
        self.assertEqual(fv.VUES_QUALITE, QUALITE)
        self.assertEqual(fv.VUES_EQUIPES, EQUIPES)
        self.assertEqual(set(fv.VUES), set(fv.VUES_FLOW) | set(EQUIPES) | set(QUALITE))
        self.assertEqual(len(fv.VUES), 9)
        self.assertEqual(len(set(fv.VUES)), 9)

    def test_les_trois_vues_sont_celles_de_la_migration(self):
        texte = (RACINE / "db" / "migrations" / "0010_quality_schema.sql").read_text(encoding="utf-8")
        for vue in QUALITE:
            self.assertIn(f"CREATE VIEW quality.{vue} AS", texte)

    def test_la_liste_montre_les_neuf_vues_avec_leur_description_dans_chaque_langue(self):
        for langue, extrait in (("fr", "qualité des stories"), ("en", "story quality")):
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                self.assertEqual(fv.main(["--language", langue, "list"]), 0)
            for vue in fv.VUES:
                self.assertIn(vue, sortie.getvalue())
            self.assertIn(extrait, sortie.getvalue())

    def test_un_nom_de_table_de_qualite_est_refuse_avant_toute_connexion(self):
        for nom in ("contents", "quality.contents", "items", "assessments", "coaching_feedback", "team_reviews", "quality_by_team; DROP TABLE x",
                    "quality.quality_by_team", "QUALITY_BY_TEAM"):
            with self.assertRaises(ValueError, msg=nom):
                fv.lire(nom)
            with mock.patch.object(db, "connect", side_effect=AssertionError("pas de connexion")):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(fv.main(["show", nom]), 1, nom)
                self.assertIn("Vue inconnue", err.getvalue())

    def test_chaque_vue_se_lit_sous_son_role_et_dans_son_schema(self):
        requetes = []

        class Curseur:
            description = [type("C", (), {"name": "team"})()]

            def fetchall(self):
                return []

        class Connexion:
            def execute(self, sql):
                requetes.append(sql)
                return Curseur()

            def close(self):
                pass

        roles = []

        def connecter(**kwargs):
            roles.append(kwargs["role"])
            return Connexion()

        with mock.patch.object(db, "connect", side_effect=connecter):
            for vue in fv.VUES_FLOW:
                fv.lire(vue)
            for vue in QUALITE:
                fv.lire(vue)
        self.assertEqual(roles, ["pmzilla_flow_views"] * 4 + ["pmzilla_quality_views"] * 3)
        self.assertEqual(requetes, [f"SELECT * FROM flow.{v}" for v in fv.VUES_FLOW] + [f"SELECT * FROM quality.{v}" for v in QUALITE])

    def test_la_commande_show_se_connecte_sous_le_role_des_vues_de_qualite(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("injoignable")) as connexion:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(fv.main(["show", "quality_by_product"]), 1)
            connexion.assert_called_once_with(role="pmzilla_quality_views")
            self.assertIn("injoignable", err.getvalue())

    def test_les_comptes_sont_masques_au_seuil_et_le_drapeau_ne_l_est_jamais(self):
        t = Messages(CATALOGS, "fr")
        noms = ["team", "item_kind", "collected", "audited", "empty_acceptance_criteria", "single_po"]
        texte = fv.rendre(noms, [("Alpha", "story", 12, 7, 6, True), ("Beta", "story", None, None, None, False)], 10, t)
        self.assertRegex(texte, r"Alpha\s+story\s+12\s+masqué\s+masqué\s+True")
        self.assertRegex(texte, r"Beta\s+story\s+masqué\s+masqué\s+masqué\s+False")
        noms = ["item_kind", "criterion_code", "origin", "link", "audited", "met", "not_met", "not_applicable", "undetermined"]
        texte = fv.rendre(noms, [("story", "c1", "core", "refinement", 20, 12, 6, None, None)], 8, t)
        self.assertRegex(texte, r"story\s+c1\s+core\s+refinement\s+20\s+12\s+masqué\s+masqué\s+masqué")

    def test_les_lignes_des_vues_de_qualite_sont_dans_l_ordre_equipe_genre_code_jamais_celui_d_un_compte(self):
        """Tâche 3.25 (M3 (a), D15) : équipe, genre, code ; pour la vue du produit genre, code. Jeu d'essai dont l'ordre des comptes
        inverserait l'ordre des noms, y compris avec une colonne de comptage placée avant les clés de tri."""
        noms = ["team", "item_kind", "criterion_code", "origin", "link", "audited", "met", "not_met", "not_applicable", "undetermined"]
        lignes = [("Beta", "story", "a-code", "core", "refinement", 9999, 9999, 9999, 9999, 9999),
                  ("Alpha", "story", "z-code", "core", "refinement", 5, 5, 5, 5, 5),
                  ("Alpha", "epic", "z-code", "core", "refinement", 6000, 6000, 6000, 6000, 6000),
                  ("Alpha", "story", "b-code", "core", "refinement", 70, 70, 70, 70, 70)]
        attendu = [("Alpha", "epic", "z-code"), ("Alpha", "story", "b-code"), ("Alpha", "story", "z-code"), ("Beta", "story", "a-code")]
        for ordre in (lignes, lignes[::-1], sorted(lignes, key=lambda l: l[5])):
            corps = fv.rendre(noms, ordre, 5, T).splitlines()[2:]
            self.assertEqual([tuple(l.split()[:3]) for l in corps], attendu)
        # une colonne de comptage placée en tête ne décide pas de l'ordre
        brouille = ["audited"] + noms[:5] + noms[6:]
        corps = fv.rendre(brouille, [(l[5],) + l[:5] + l[6:] for l in lignes], 5, T).splitlines()[2:]
        self.assertEqual([tuple(l.split()[1:4]) for l in corps], attendu)

    def test_l_ordre_de_la_vue_du_produit_est_genre_puis_code(self):
        noms = ["item_kind", "criterion_code", "origin", "link", "audited", "met", "not_met", "not_applicable", "undetermined"]
        lignes = [("story", "b", "core", "refinement", 1000, 1000, 1000, 1000, 1000), ("epic", "z", "core", "refinement", 5, 5, 5, 5, 5),
                  ("story", "a", "core", "refinement", 50, 50, 50, 50, 50)]
        corps = fv.rendre(noms, lignes, 5, T).splitlines()[2:]
        self.assertEqual([tuple(l.split()[:2]) for l in corps], [("epic", "z"), ("story", "a"), ("story", "b")])

    def test_l_ordre_de_la_couverture_est_equipe_puis_genre(self):
        noms = ["team", "item_kind", "collected", "audited", "empty_acceptance_criteria", "single_po"]
        lignes = [("Beta", "epic", 90, 90, 90, True), ("Alpha", "story", 5, 5, 5, False), ("Alpha", "epic", 700, 700, 700, False)]
        corps = fv.rendre(noms, lignes, 5, T).splitlines()[2:]
        self.assertEqual([tuple(l.split()[:2]) for l in corps], [("Alpha", "epic"), ("Alpha", "story"), ("Beta", "epic")])

    def test_les_colonnes_de_comptage_de_qualite_sont_celles_de_la_migration(self):
        self.assertEqual(set(fv.COLONNES_COMPTE), {"tickets", "links", "collected", "audited", "empty_acceptance_criteria", "met", "not_met",
                                                    "not_applicable", "undetermined"})
        sql = (RACINE / "db" / "migrations" / "0010_quality_schema.sql").read_text(encoding="utf-8")
        for colonne in ("collected", "audited", "empty_acceptance_criteria", "met", "not_met", "not_applicable", "undetermined"):
            self.assertRegex(sql, rf"mask_count\([^;]*?\) AS {colonne}\b")


class VuesDesNomsDEquipe(unittest.TestCase):
    """Change team-names-readable (tâche 2.4, conception D2, D3, D7, D10) : deux vues de plus dans la liste fermée, cellules structurées."""

    def test_les_deux_vues_sont_celles_de_la_migration_0014(self):
        candidats = [p for p in (RACINE / "db" / "migrations").glob("*_flow_team_name_views.sql")]
        self.assertEqual(len(candidats), 1)
        self.assertTrue(candidats[0].name.startswith("0014_"))
        texte = candidats[0].read_text(encoding="utf-8")
        self.assertEqual(len(fv.VUES_EQUIPES), 2)
        for vue in fv.VUES_EQUIPES:
            self.assertIn(f"CREATE VIEW flow.{vue} AS", texte)

    def test_un_nom_proche_ou_qualifie_est_refuse_avant_toute_connexion(self):
        for nom in ("teams", "v_team", "flow.v_teams", "V_TEAMS", "v_teams; DROP TABLE x", "v_team_jira_id", "flow.v_team_jira_ids",
                    "flow.teams", "v_team_tickets_seen"):
            with self.assertRaises(ValueError, msg=nom):
                fv.lire(nom)
            with mock.patch.object(db, "connect", side_effect=AssertionError("pas de connexion")):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(fv.main(["show", nom]), 1, nom)
                self.assertIn("Vue inconnue", err.getvalue())

    def test_les_deux_vues_se_lisent_sous_le_role_des_vues_dans_le_schema_flow(self):
        requetes, roles = [], []

        class Curseur:
            description = [type("C", (), {"name": "team"})()]

            def fetchall(self):
                return []

        class Connexion:
            def execute(self, sql):
                requetes.append(sql)
                return Curseur()

            def close(self):
                pass

        def connecter(**kwargs):
            roles.append(kwargs["role"])
            return Connexion()

        with mock.patch.object(db, "connect", side_effect=connecter):
            for vue in EQUIPES:
                fv.lire(vue)
        self.assertEqual(roles, ["pmzilla_flow_views"] * 2)
        self.assertEqual(requetes, [f"SELECT * FROM flow.{v}" for v in EQUIPES])

    def test_cellule_d_un_compte_au_dessus_du_seuil(self):
        self.assertEqual(fv.cellule("tickets", 12, 5), {"value": 12})
        self.assertEqual(fv.cellule("tickets", 5, 5), {"value": 5})
        self.assertEqual(fv.cellule("links", 40, 10), {"value": 40})

    def test_cellule_masquee_avec_sa_raison_et_son_seuil(self):
        attendu = {"value": None, "masked": "under_threshold", "threshold": 5}
        self.assertEqual(fv.cellule("tickets", 3, 5), attendu)
        self.assertEqual(fv.cellule("tickets", None, 5), attendu)                 # un nul de la vue est masqué de la même façon
        self.assertEqual(fv.cellule("tickets", 0, 5), attendu)
        self.assertEqual(fv.cellule("tickets", 7, 8), {"value": None, "masked": "under_threshold", "threshold": 8})

    def test_les_autres_colonnes_ne_sont_jamais_masquees(self):
        self.assertEqual(fv.cellule("jira_team_id", "21", 5), {"value": "21"})
        self.assertEqual(fv.cellule("team_type", "Development Team", 99), {"value": "Development Team"})
        self.assertEqual(fv.cellule("team_type", None, 5), {"value": None})
        self.assertEqual(fv.cellule("team", "Alpha", 5), {"value": "Alpha"})

    def test_show_v_teams_imprime_le_type_tel_que_stocke_vide_si_nul_et_masque_les_comptes(self):
        t = Messages(CATALOGS, "fr")
        texte = fv.rendre(["team", "team_type", "tickets"],
                          [("Alpha", "Development Team", 12), ("Beta", None, 2), ("Gamma", "Other Team", None)], 5, t)
        self.assertRegex(texte, r"Alpha\s+Development Team\s+12")
        self.assertRegex(texte, r"Beta\s+masqué")
        self.assertNotIn("None", texte)
        self.assertRegex(texte, r"Gamma\s+Other Team\s+masqué")

    def test_show_v_team_jira_ids_ne_masque_pas_l_identifiant(self):
        t = Messages(CATALOGS, "fr")
        texte = fv.rendre(["team", "jira_team_id", "tickets"], [("Alpha", "12", 20), ("Beta", "21", 3), ("Gamma", "7", None)], 10, t)
        self.assertRegex(texte, r"Alpha\s+12\s+20")
        self.assertRegex(texte, r"Beta\s+21\s+masqué")
        self.assertRegex(texte, r"Gamma\s+7\s+masqué")

    def test_rendre_s_appuie_sur_cellule(self):
        t = Messages(CATALOGS, "fr")
        with mock.patch.object(fv, "cellule", wraps=fv.cellule) as appels:
            fv.rendre(["team", "tickets"], [("Alpha", 12), ("Beta", 1)], 5, t)
        colonnes = {c.args[0] for c in appels.call_args_list}
        self.assertEqual(colonnes, {"team", "tickets"})
        self.assertEqual(appels.call_count, 4)

    def test_la_liste_montre_les_deux_vues(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(fv.main(["list"]), 0)
        for vue in EQUIPES:
            self.assertIn(vue, sortie.getvalue())


class AvecBase(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._nettoyer)
        self.admin.execute(f'CREATE DATABASE "{self.nom}"')
        self.url = base.url_vers(self.nom)
        self.conn = db.connect(self.url, password=base.MOT_DE_PASSE)
        db.migrer(self.conn, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        self.conn.commit()
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        for i in range(12):
            self.conn.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id) "
                              "VALUES (%s, 'PROJ', 'Story', 'Closed', 'Done', now() - interval '20 days', now() - interval '2 days', now(), 1)",
                              (f"PROJ-{i}",))
        for i in range(12, 14):
            self.conn.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, updated_at, team_id) "
                              "VALUES (%s, 'PROJ', 'Story', 'Open', 'To Do', now(), now(), 2)", (f"PROJ-{i}",))
        self.conn.execute("RESET ROLE")
        self.conn.commit()

    def _nettoyer(self):
        with contextlib.suppress(Exception):
            self.conn.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom}" WITH (FORCE)')
        self.admin.close()

    def connexion_simulee(self, **_):
        c = CONNECT_REEL(self.url, password=base.MOT_DE_PASSE, autocommit=True)
        c.execute("SET ROLE pmzilla_flow_views")
        return c

    def test_lecture_et_masquage_de_bout_en_bout(self):
        with mock.patch.object(db, "connect", side_effect=self.connexion_simulee):
            noms, lignes = fv.lire("v_team_status")
            self.assertEqual(noms, ["team", "type", "status_category", "status", "tickets"])
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                self.assertEqual(fv.main(["show", "v_team_status"]), 0)
            texte = sortie.getvalue()
            self.assertIn("Alpha", texte)
            self.assertRegex(texte, r"Alpha\s+Story\s+Done\s+Closed\s+12")
            self.assertRegex(texte, r"Beta\s+Story\s+To Do\s+Open\s+masqué")      # 2 tickets : masqués
            self.assertNotIn("PROJ-", texte)
            sortie, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(err):
                fv.main(["show", "v_team_status", "--min-cell", "20"])
            self.assertRegex(sortie.getvalue(), r"Alpha\s+Story\s+Done\s+Closed\s+masqué")
            self.assertIn("Seuil de masquage : 20 tickets", err.getvalue())

    def test_lecture_de_bout_en_bout_des_deux_vues_des_noms_d_equipe(self):
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("UPDATE flow.teams SET team_type = 'Development Team' WHERE name = 'Alpha'")
        self.conn.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) "
                          "SELECT key, team_id, 1 FROM flow.issues")
        self.conn.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries) VALUES ('export', 1, true)")
        self.conn.execute("INSERT INTO flow.raw_issue_snapshots (issue_key, run_id, updated_at, project, type, status, created_at, content_hash, "
                          "teams) SELECT key, (SELECT max(id) FROM flow.raw_runs), now(), 'PROJ', 'Story', 'Open', now(), 'h', "
                          "CASE WHEN team_id = 1 THEN '[{\"name\": \"Alpha\", \"jira_team_id\": \"12\"}]'::jsonb "
                          "ELSE '[{\"name\": \"Beta\", \"jira_team_id\": \"21\"}]'::jsonb END FROM flow.issues")
        self.conn.execute("RESET ROLE")
        self.conn.commit()
        with mock.patch.object(db, "connect", side_effect=self.connexion_simulee):
            noms, _ = fv.lire("v_teams")
            self.assertEqual(noms, ["team", "team_type", "tickets"])
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                self.assertEqual(fv.main(["show", "v_teams"]), 0)
            self.assertRegex(sortie.getvalue(), r"Alpha\s+Development Team\s+12")
            self.assertRegex(sortie.getvalue(), r"Beta\s+masqué")
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                self.assertEqual(fv.main(["show", "v_team_jira_ids"]), 0)
            self.assertRegex(sortie.getvalue(), r"Alpha\s+12\s+12")
            self.assertRegex(sortie.getvalue(), r"Beta\s+21\s+masqué")
            self.assertNotIn("PROJ-", sortie.getvalue())

    def test_le_chemin_de_lecture_ne_permet_pas_de_lire_une_table(self):
        c = self.connexion_simulee()
        with self.assertRaises(db.psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT key FROM flow.issues")
        c.close()

    def test_le_role_des_vues_de_qualite_lit_les_vues_et_aucune_table(self):
        """R-78 : la connexion sous le rôle des vues de qualité est simulée par SET ROLE (son mot de passe réel n'est jamais utilisé)."""
        def simulee(**_):
            connexion = CONNECT_REEL(self.url, password=base.MOT_DE_PASSE, autocommit=True)
            connexion.execute("SET ROLE pmzilla_quality_views")
            return connexion

        c = simulee()
        for vue in QUALITE:
            self.assertEqual(c.execute(f"SELECT count(*) FROM quality.{vue}").fetchone()[0], 0, vue)
        with mock.patch.object(db, "connect", side_effect=simulee):
            noms, lignes = fv.lire("quality_by_product")
        self.assertEqual((noms[:4], lignes), (["item_kind", "criterion_code", "origin", "link"], []))
        for requete in ("SELECT * FROM quality.contents", "SELECT * FROM quality.items", "SELECT key FROM flow.issues"):
            with self.assertRaises(db.psycopg.errors.InsufficientPrivilege, msg=requete):
                c.execute(requete)
        c.close()


class SurvivantsDeMutation(unittest.TestCase):
    """Change masking-mutation-tests (tâche 6.2) : un test par mutant survivant connu, sans base (connexion simulée)."""

    def connecter(self, noms, lignes):
        class Curseur:
            description = [type("C", (), {"name": n})() for n in noms]

            def fetchall(self):
                return list(lignes)

        class Connexion:
            def execute(self, sql):
                return Curseur()

            def close(self):
                pass

        return mock.patch.object(db, "connect", side_effect=lambda **kwargs: Connexion())

    def test_lire_rend_les_noms_et_les_lignes_de_la_vue(self):
        # mutant tué : `return noms, lignes` devenu `return None` (lire)
        with self.connecter(["team", "tickets"], [("Alpha", 12)]):
            self.assertEqual(fv.lire("v_team_status"), (["team", "tickets"], [("Alpha", 12)]))

    def test_show_rend_zero_exactement_et_imprime_la_vue_masquee(self):
        # mutant tué : `return 0` de la commande show devenu `return None` (main)
        sortie = io.StringIO()
        with mock.patch.object(fv, "seuil_configure", return_value=5), self.connecter(["team", "tickets"], [("Alpha", 12), ("Beta", 3)]):
            with contextlib.redirect_stdout(sortie):
                code = fv.main(["show", "v_team_status"])
        self.assertEqual(code, 0)
        self.assertIsNotNone(code)
        self.assertRegex(sortie.getvalue(), r"Alpha\s+12")
        self.assertRegex(sortie.getvalue(), r"Beta\s+masqué")

    def test_show_avec_seuil_releve_masque_au_seuil_de_l_option(self):
        sortie, err = io.StringIO(), io.StringIO()
        with mock.patch.object(fv, "seuil_configure", return_value=5), self.connecter(["team", "tickets"], [("Alpha", 12)]):
            with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(err):
                self.assertEqual(fv.main(["show", "v_team_status", "--min-cell", "20"]), 0)
        self.assertRegex(sortie.getvalue(), r"Alpha\s+masqué")
        self.assertIn("Seuil de masquage : 20 tickets (une cellule sous ce seuil s'écrit « masqué »).", err.getvalue())

    def test_show_au_plancher_ne_rappelle_pas_le_seuil(self):
        err = io.StringIO()
        with mock.patch.object(fv, "seuil_configure", return_value=5), self.connecter(["team", "tickets"], [("Alpha", 3)]):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(fv.main(["show", "v_team_status"]), 0)
        self.assertEqual(err.getvalue(), "")

    def test_sans_commande_l_analyse_des_arguments_refuse(self):
        # mutant tué : `required=True` devenu `required=False` (main) : sans commande, refus d'argparse (code 2), jamais une autre erreur
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as sortie:
            fv.main([])
        self.assertEqual(sortie.exception.code, 2)

    def test_les_lignes_sont_triees_le_nul_compte_comme_texte_vide(self):
        # mutants tués : `x is None` devenu `x is not None` ou `not (x is None)` dans la clé de tri (rendre)
        texte = fv.rendre(["team", "tickets"], [("Gamma", 7), ("Alpha", 12), (None, 20)], 5, T)
        lignes = texte.splitlines()
        self.assertEqual(lignes[2].strip(), "20")                     # équipe nulle : clé ("", "20"), avant toute autre
        self.assertTrue(lignes[3].startswith("Alpha"))
        self.assertTrue(lignes[4].startswith("Gamma"))
        self.assertEqual(len(lignes), 5)

    def test_largeur_de_colonne_la_plus_grande_des_valeurs_et_du_nom(self):
        # mutant tué : `max` devenu `min` dans le calcul des largeurs (rendre)
        texte = fv.rendre(["team", "tickets"], [("Alphabetique", 12)], 5, T)
        self.assertEqual(texte.splitlines(), ["team          tickets", "------------  -------", "Alphabetique  12"])


if __name__ == "__main__":
    unittest.main()
