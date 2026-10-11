"""
Tests de la migration 0006 (schéma cases, lot 2) sur une base jetable pmzilla_test_<hex>.

    uv run --with "psycopg[binary]" --with numpy --with httpx python -m unittest discover -s tests/db -v

Les tests avec base ne touchent que la base jetable (créée puis supprimée dans tous les cas), jamais les schémas réels ; ils sont
sautés si la base manque. Aucune donnée réelle : expériences et vecteurs inventés.
"""
import contextlib
import json
import secrets
import unittest

import test_db as base          # noqa: E402  (même dossier : connexion, base jetable, mot de passe)
from test_db import db          # noqa: E402

TABLES = {"experiments", "experiment_notes", "cases"}
VECTEUR = "[" + ",".join(["1"] + ["0"] * 1023) + "]"
FICHIER = "0006_cases_experiments.sql"


class SansBase(unittest.TestCase):
    def texte(self):
        return (db.DOSSIER_MIGRATIONS / FICHIER).read_text(encoding="utf-8")

    def test_migration_0006_presente_sans_donnee_ni_mot_de_passe(self):
        self.assertIn(FICHIER, [m.nom for m in db.lister_migrations()])
        texte = self.texte()
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : cases")
        self.assertNotRegex(texte, r"(?im)^\s*INSERT\s+INTO")
        self.assertNotRegex(texte, r"(?i)password")
        self.assertNotRegex(texte, r"(?i)CREATE\s+ROLE|ALTER\s+ROLE")

    def test_travailleurs_paralleles_coupes_avant_le_premier_index_bm25(self):
        texte = self.texte()
        self.assertIn("SET LOCAL max_parallel_maintenance_workers = 0;", texte)
        self.assertIn("USING bm25", texte)
        self.assertLess(texte.index("max_parallel_maintenance_workers"), texte.index("USING bm25"))
        self.assertLess(texte.index("SET LOCAL ROLE pmzilla_owner;"), texte.index("CREATE TABLE"))
        self.assertEqual(texte.count("pdb.simple('ascii_folding=true')"), 2)
        self.assertIn("RESET ROLE;", texte)


class SchemaCases(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        self.ouvertes = []
        c = self.conn()
        db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()

    def _supprimer(self):
        for c in self.ouvertes:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def conn(self):
        c = db.connect(self.url, password=base.MOT_DE_PASSE)
        self.ouvertes.append(c)
        return c

    def experience(self, c, **champs):
        """Insère une expérience inventée (rôle pmzilla_cases) et rend son id ; `champs` remplace les valeurs par défaut."""
        valeurs = {"author": "auteur-test", "started_on": "2027-01-04", "posture": "delivery", "status": "running",
                   "problem": "Les prévisions de livraison dérapent", "context": json.dumps({"equipe": "type A"}),
                   "tested": "Une revue hebdomadaire du flux", "expected_signal": "Moins de tickets bloqués",
                   "success_criterion": "Moins de 3 tickets bloqués par semaine", "review_due": "2027-02-15",
                   "embedding": VECTEUR}
        valeurs.update(champs)
        c.execute("SET ROLE pmzilla_cases")
        colonnes = ", ".join(valeurs)
        marques = ", ".join(["%s::halfvec" if k == "embedding" else "%s" for k in valeurs])
        return c.execute(f"INSERT INTO cases.experiments ({colonnes}) VALUES ({marques}) RETURNING id", tuple(valeurs.values())).fetchone()[0]

    def cas(self, c, experience_id, **champs):
        valeurs = {"experiment_id": experience_id, "author": "auteur-test", "posture": "delivery",
                   "problem": "Les prévisions de livraison dérapent", "context": json.dumps({}),
                   "tested": "Une revue hebdomadaire du flux", "expected_signal": "Moins de tickets bloqués",
                   "success_criterion": "Moins de 3 tickets bloqués par semaine", "launched_on": "2027-01-04",
                   "reviewed_on": "2027-02-15", "outcome": "worked", "embedding": VECTEUR}
        valeurs.update(champs)
        c.execute("SET ROLE pmzilla_cases")
        colonnes = ", ".join(valeurs)
        marques = ", ".join(["%s::halfvec" if k == "embedding" else "%s" for k in valeurs])
        return c.execute(f"INSERT INTO cases.cases ({colonnes}) VALUES ({marques}) RETURNING id", tuple(valeurs.values())).fetchone()[0]

    def refuse(self, c, role, ordre, params=None):
        """Exécute l'ordre sous `role`, attend une erreur de la base, annule."""
        c.rollback()
        c.execute(f"SET ROLE {role}")
        with self.assertRaises(Exception):
            c.execute(ordre, params)
        c.rollback()

    # --- 2.2 structure -------------------------------------------------------------------------------------------------------

    def test_trois_tables_colonnes_index_et_proprietaire(self):
        c = self.conn()
        noms = {r[0] for r in c.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                        "WHERE n.nspname = 'cases' AND c.relkind = 'r'")}
        self.assertEqual(noms, TABLES)
        self.assertEqual({r[0] for r in c.execute("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'cases'")}, {"pmzilla_owner"})
        colonnes = {(r[0], r[1]): r[2] for r in c.execute("SELECT table_name, column_name, data_type FROM information_schema.columns "
                                                          "WHERE table_schema = 'cases'")}
        for table in ("experiments", "cases"):
            for col, type_ in (("context", "jsonb"), ("hypotheses", "jsonb"), ("references_used", "jsonb"), ("embedding", "USER-DEFINED"),
                               ("success_criterion", "text"), ("fts_text", "text"), ("author", "text")):
                self.assertEqual(colonnes[(table, col)], type_, (table, col))
        self.assertEqual(colonnes[("experiments", "review_due")], "date")
        self.assertEqual(colonnes[("experiments", "postponements")], "integer")
        self.assertEqual(colonnes[("cases", "history")], "jsonb")
        self.assertEqual(colonnes[("cases", "reviewed_on")], "date")
        self.assertEqual(colonnes[("experiment_notes", "noted_on")], "date")
        generees = {(r[0], r[1]) for r in c.execute("SELECT table_name, column_name FROM information_schema.columns "
                                                    "WHERE table_schema = 'cases' AND is_generated = 'ALWAYS' AND column_name = 'fts_text'")}
        self.assertEqual(generees, {("experiments", "fts_text"), ("cases", "fts_text")})
        nullable = {(r[0], r[1]): r[2] for r in c.execute("SELECT table_name, column_name, is_nullable FROM information_schema.columns "
                                                          "WHERE table_schema = 'cases' AND column_name = 'embedding'")}
        self.assertEqual(nullable, {("experiments", "embedding"): "YES", ("cases", "embedding"): "NO"})
        index = {r[0]: r[1] for r in c.execute("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'cases'")}
        self.assertLessEqual({"experiments_embedding_hnsw", "experiments_author_status_due", "experiments_bm25", "experiment_notes_experiment_noted",
                              "cases_embedding_hnsw", "cases_outcome", "cases_bm25"}, set(index))
        for nom in ("experiments_embedding_hnsw", "cases_embedding_hnsw"):
            self.assertIn("hnsw", index[nom])
            self.assertIn("halfvec_cosine_ops", index[nom])
        for nom in ("experiments_bm25", "cases_bm25"):
            self.assertIn("bm25", index[nom])
            self.assertIn("fts_text", index[nom])
        self.assertIn("(author, status, review_due)", index["experiments_author_status_due"])
        self.assertIn("(experiment_id, noted_on)", index["experiment_notes_experiment_noted"])
        self.assertIn("(outcome)", index["cases_outcome"])

    def test_tables_vides_apres_migration(self):
        c = self.conn()
        for table in TABLES:
            self.assertEqual(c.execute(f"SELECT count(*) FROM cases.{table}").fetchone()[0], 0, table)

    def test_migration_rejouee_sans_effet(self):
        c = self.conn()
        etat = db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()
        self.assertEqual(getattr(etat, "en_attente", []) or [], [])
        for table in TABLES:
            self.assertEqual(c.execute(f"SELECT count(*) FROM cases.{table}").fetchone()[0], 0, table)

    # --- 2.3 contraintes -----------------------------------------------------------------------------------------------------

    def test_valeurs_refusees_sur_experiments(self):
        c = self.conn()
        for champs in ({"status": "paused"}, {"posture": "critic"}, {"review_due": "2026-12-31"}, {"problem": "  "},
                       {"tested": ""}, {"expected_signal": " "}, {"success_criterion": ""}, {"author": " "},
                       {"context": json.dumps([1])}, {"hypotheses": json.dumps({"a": 1})}, {"references_used": json.dumps("x")},
                       {"postponements": -1}):
            with self.subTest(champs=champs):
                c.rollback()
                with self.assertRaises(Exception):
                    self.experience(c, **champs)
                c.rollback()
        c.rollback()
        self.experience(c, posture="none", hypotheses=json.dumps(["h1"]), references_used=json.dumps([]))     # valeurs limites acceptées
        self.experience(c, posture=None)
        c.rollback()

    def test_valeurs_refusees_sur_cas(self):
        c = self.conn()
        exp = self.experience(c)
        c.commit()
        for champs in ({"outcome": "great"}, {"confidence": "certain"}, {"reviewed_on": "2026-12-31"},
                       {"outcome": "dropped"}, {"outcome": "dropped", "drop_reason": "  "}, {"history": json.dumps({})}):
            with self.subTest(champs=champs):
                with self.assertRaises(Exception):
                    self.cas(c, exp, **champs)
                c.rollback()
        self.cas(c, exp, outcome="dropped", drop_reason="Le sujet a disparu", confidence="low")      # valeurs limites acceptées
        c.rollback()

    def test_un_seul_cas_par_experience_et_note_d_une_experience_inconnue(self):
        c = self.conn()
        exp = self.experience(c)
        self.cas(c, exp)
        c.commit()
        with self.assertRaises(Exception):
            c.execute("SET ROLE pmzilla_cases")
            self.cas(c, exp, outcome="failed")
        c.rollback()
        c.execute("SET ROLE pmzilla_cases")
        c.execute("INSERT INTO cases.experiment_notes (experiment_id, noted_on, note) VALUES (%s, '2027-01-20', 'Premier signal')", (exp,))
        for ordre, params in (("INSERT INTO cases.experiment_notes (experiment_id, noted_on, note) VALUES (999, '2027-01-20', 'x')", None),
                              ("INSERT INTO cases.experiment_notes (experiment_id, noted_on, note) VALUES (%s, '2027-01-20', ' ')", (exp,))):
            with self.subTest(ordre=ordre):
                c.commit()
                c.execute("SET ROLE pmzilla_cases")
                with self.assertRaises(Exception):
                    c.execute(ordre, params)
                c.rollback()
        c.rollback()

    def test_le_critere_de_reussite_n_est_jamais_reecrit(self):
        c = self.conn()
        exp = self.experience(c)
        cas_id = self.cas(c, exp)
        c.commit()
        for ordre, params in (("UPDATE cases.experiments SET success_criterion = 'Autre critère' WHERE id = %s", (exp,)),
                              ("UPDATE cases.cases SET success_criterion = 'Autre critère' WHERE id = %s", (cas_id,))):
            with self.subTest(ordre=ordre):
                self.refuse(c, "pmzilla_cases", ordre, params)
        c.execute("SET ROLE pmzilla_cases")
        # une autre colonne reste modifiable ; le même critère réécrit à l'identique aussi
        c.execute("UPDATE cases.experiments SET status = 'closed', review_due = '2027-03-01' WHERE id = %s", (exp,))
        c.execute("UPDATE cases.experiments SET success_criterion = success_criterion WHERE id = %s", (exp,))
        c.execute("UPDATE cases.cases SET what_got_stuck = 'Rien de bloquant' WHERE id = %s", (cas_id,))
        self.assertEqual(c.execute("SELECT status FROM cases.experiments WHERE id = %s", (exp,)).fetchone()[0], "closed")
        self.assertEqual(c.execute("SELECT success_criterion FROM cases.experiments WHERE id = %s", (exp,)).fetchone()[0],
                         "Moins de 3 tickets bloqués par semaine")
        c.rollback()

    # --- 2.3 recherche et droits ---------------------------------------------------------------------------------------------

    def test_bm25_trouve_un_mot_accentue_ecrit_sans_accent_en_lecture_seule(self):
        c = self.conn()
        exp = self.experience(c, problem="Les équipes manquent de visibilité", chosen_path="Un tableau partagé")
        self.cas(c, exp, problem="Les équipes manquent de visibilité")
        c.commit()
        c.execute("SET ROLE pmzilla_cases_ro")
        for table in ("experiments", "cases"):
            for question in ("equipes", "ÉQUIPES", "visibilite"):
                with self.subTest(table=table, question=question):
                    lignes = c.execute(f"SELECT id, pdb.score(id) FROM cases.{table} WHERE fts_text ||| %s ORDER BY pdb.score(id) DESC LIMIT 5",
                                       (question,)).fetchall()
                    self.assertEqual([i for i, _ in lignes], [1])
                    self.assertGreater(lignes[0][1], 0)
            self.assertEqual(c.execute(f"SELECT id FROM cases.{table} WHERE fts_text ||| 'tableau'").fetchall(),
                             [(1,)] if table == "experiments" else [])        # le chemin retenu est indexé, comme `tested`
        # recherche vectorielle permise au rôle de lecture
        self.assertEqual(c.execute("SELECT id FROM cases.cases ORDER BY embedding <=> %s::halfvec LIMIT 1", (VECTEUR,)).fetchall(), [(1,)])
        c.rollback()

    def test_le_role_de_lecture_ne_fait_que_lire(self):
        c = self.conn()
        exp = self.experience(c)
        self.cas(c, exp)
        c.commit()
        c.execute("SET ROLE pmzilla_cases_ro")
        self.assertEqual(c.execute("SELECT count(*) FROM cases.experiments").fetchone()[0], 1)
        self.assertEqual(c.execute("SELECT count(*) FROM cases.cases").fetchone()[0], 1)
        c.rollback()
        for ordre in ("INSERT INTO cases.experiment_notes (experiment_id, noted_on, note) VALUES (1, '2027-01-20', 'x')",
                      "DELETE FROM cases.cases", "UPDATE cases.experiments SET status = 'closed'", "CREATE TABLE cases.pirate (x int)"):
            with self.subTest(ordre=ordre):
                self.refuse(c, "pmzilla_cases_ro", ordre)

    def test_le_role_d_ecriture_ecrit_mais_ne_cree_ni_ne_lit_ailleurs(self):
        c = self.conn()
        exp = self.experience(c)          # l'insertion passe
        c.execute("INSERT INTO cases.experiment_notes (experiment_id, noted_on, note) VALUES (%s, '2027-01-20', 'Note')", (exp,))
        c.rollback()
        for ordre in ("CREATE TABLE cases.pirate (x int)", "CREATE TABLE public.pirate (x int)", "SELECT count(*) FROM knowledge.books",
                      "SELECT count(*) FROM flow.issues"):
            with self.subTest(ordre=ordre):
                self.refuse(c, "pmzilla_cases", ordre)
        for ordre in ("SELECT count(*) FROM knowledge.books", "SELECT count(*) FROM flow.issues"):
            with self.subTest(role="pmzilla_cases_ro", ordre=ordre):
                self.refuse(c, "pmzilla_cases_ro", ordre)


if __name__ == "__main__":
    unittest.main()
