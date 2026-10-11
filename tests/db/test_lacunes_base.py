"""
Tests des lacunes de la section « database » (openspec/test-gaps.md) : tranches d'âge et semaines des vues flow, colonne
has_history (migration 0003), indice de connexion sans mot de passe, commande role-password.

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base tournent toujours (faux Trousseau, fausse saisie, faux connect). Les autres utilisent la base jetable de
test_flow_schema.py (même fixture) et sont sautés quand aucun mot de passe ou aucune base n'est disponible. Données inventées.
"""
import contextlib
import io
import os
import unittest
import unittest.mock

import test_db as base          # noqa: E402
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402  (module importé, pas la classe : ses tests ne tournent pas deux fois)


class BaseJetable(unittest.TestCase):
    """Même base jetable que SchemaFlow : migrations appliquées, supprimée à la fin."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn

    def inserer(self, c, cle, equipe_id, cree=None, resolu=None):
        c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id) "
                  "VALUES (%s, 'PROJ', 'Story', 'X', %s, COALESCE(%s::timestamptz, now()), %s::timestamptz, now(), %s)",
                  (cle, "Done" if resolu else "To Do", cree, resolu, equipe_id))


class VueAgeDesTicketsOuverts(BaseJetable):
    def test_bornes_et_libelles_des_tranches(self):
        """now() est figé pendant une transaction : l'âge d'un ticket créé à now() - X est exactement X (horloge maîtrisée).
        Chaque borne a sa propre équipe, cinq tickets (le masquage cache les cellules de moins de cinq)."""
        cas = [("0 seconds", "0-7 j"), ("7 days 23 hours 59 minutes", "0-7 j"), ("8 days", "8-30 j"),
               ("30 days 23 hours 59 minutes", "8-30 j"), ("31 days", "31-90 j"),
               ("90 days 23 hours 59 minutes", "31-90 j"), ("91 days", "91 j et plus"), ("400 days", "91 j et plus")]
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        for i, (age, _) in enumerate(cas, start=1):
            c.execute("INSERT INTO flow.teams (name) VALUES (%s)", (f"T{i}",))
            for k in range(5):
                self.inserer(c, f"PROJ-{i}-{k}", i, cree=None)
                c.execute("UPDATE flow.issues SET created_at = now() - %s::interval WHERE key = %s", (age, f"PROJ-{i}-{k}"))
        c.execute("RESET ROLE")
        c.execute("SET ROLE pmzilla_flow_views")
        lues = {r[0]: (r[1], r[2], r[3]) for r in c.execute("SELECT team, status_category, age_bucket, tickets FROM flow.v_team_open_age")}
        c.execute("RESET ROLE")
        for i, (age, tranche) in enumerate(cas, start=1):
            self.assertEqual(lues[f"T{i}"], ("To Do", tranche, 5), f"âge {age}")

    def test_un_ticket_resolu_n_est_pas_dans_la_vue(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('T1')")
        for k in range(5):
            self.inserer(c, f"PROJ-{k}", 1, cree="2020-01-01T00:00:00+00:00", resolu="2020-02-01T00:00:00+00:00")
        c.execute("RESET ROLE")
        c.execute("SET ROLE pmzilla_flow_views")
        self.assertEqual(c.execute("SELECT count(*) FROM flow.v_team_open_age").fetchone()[0], 0)
        c.execute("RESET ROLE")


class VueSemainesResolues(BaseJetable):
    def test_semaine_tronquee_en_utc_autour_de_minuit(self):
        """Le lundi 2026-03-02 00:00 UTC ouvre une semaine. Les fuseaux de saisie et celui de la session ne changent rien."""
        avant = ["2026-03-01T23:59:59+00:00", "2026-03-01T23:59:59+00:00", "2026-03-01T23:59:59+00:00",
                 "2026-03-02T01:00:00+02:00", "2026-03-02T01:30:00+02:00"]        # 23:00 et 23:30 UTC, dimanche
        apres = ["2026-03-02T00:00:00+00:00", "2026-03-02T00:00:00+00:00", "2026-03-02T00:00:00+00:00",
                 "2026-03-01T22:00:00-05:00", "2026-03-01T22:30:00-05:00"]        # 03:00 et 03:30 UTC, lundi
        c = self.conn()
        c.execute("SET TIME ZONE 'Pacific/Auckland'")                              # session loin de l'UTC
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha')")
        for i, quand in enumerate(avant + apres):
            self.inserer(c, f"PROJ-{i}", 1, cree="2026-01-01T00:00:00+00:00", resolu=quand)
        c.execute("RESET ROLE")
        c.execute("SET ROLE pmzilla_flow_views")
        lues = {str(r[0]): r[1] for r in c.execute("SELECT week_start, tickets FROM flow.v_team_weekly_resolved")}
        c.execute("RESET ROLE")
        self.assertEqual(lues, {"2026-02-23": 5, "2026-03-02": 5})


class ColonneHasHistory(BaseJetable):
    def test_colonne_booleenne_non_nulle_faux_par_defaut(self):
        c = self.conn()
        ligne = c.execute("SELECT data_type, is_nullable, column_default FROM information_schema.columns "
                          "WHERE table_schema = 'flow' AND table_name = 'issues' AND column_name = 'has_history'").fetchone()
        self.assertIsNotNone(ligne, "colonne flow.issues.has_history absente")
        self.assertEqual(ligne, ("boolean", "NO", "false"))

    def test_un_ticket_insere_sans_la_colonne_vaut_faux(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        self.inserer(c, "PROJ-1", None, cree="2026-01-01T00:00:00+00:00")
        self.assertEqual(c.execute("SELECT has_history FROM flow.issues WHERE key = 'PROJ-1'").fetchone(), (False,))
        c.execute("RESET ROLE")                                       # l'import écrit avec l'exécuteur, comme ici
        c.execute("UPDATE flow.issues SET has_history = true WHERE key = ANY(%s) AND NOT has_history", (["PROJ-1"],))
        self.assertEqual(c.execute("SELECT has_history FROM flow.issues WHERE key = 'PROJ-1'").fetchone(), (True,))
        with self.assertRaises(db.psycopg.errors.NotNullViolation):
            with c.transaction():
                c.execute("UPDATE flow.issues SET has_history = NULL WHERE key = 'PROJ-1'")


class SansBase(unittest.TestCase):
    def test_migration_0003_ajoute_la_colonne_sans_donnee(self):
        texte = (db.DOSSIER_MIGRATIONS / "0003_flow_has_history.sql").read_text(encoding="utf-8")
        sql = "\n".join(l.split("--")[0] for l in texte.splitlines())
        self.assertRegex(sql, r"(?i)ALTER TABLE flow\.issues ADD COLUMN has_history boolean NOT NULL DEFAULT false")
        self.assertNotRegex(sql, r"(?i)\bINSERT\s+INTO")

    def test_indice_sans_mot_de_passe_nomme_le_trousseau_et_la_variable(self):
        if db.psycopg is None:
            self.skipTest("psycopg absent")
        env = {k: v for k, v in os.environ.items() if not k.startswith("PMZILLA_LAB_DB_PASSWORD")}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            os.environ[db.VARIABLE_SECURITY] = "/inexistant/security"      # Trousseau vide, jamais le vrai
            with self.assertRaises(db.ErreurBase) as ctx:
                db.connect("postgresql://postgres@127.0.0.1:1/pmzilla", timeout=2)
            self.assertIn(f"Aucun mot de passe trouvé (Trousseau {db.SERVICE_TROUSSEAU}, puis {db.VARIABLE_MOT_DE_PASSE}).",
                          str(ctx.exception))
            with self.assertRaises(db.ErreurBase) as ctx:
                db.connect("postgresql://postgres@127.0.0.1:1/pmzilla", timeout=2, role="pmzilla_flow_views")
            self.assertIn("Trousseau pmzilla-lab-db-pmzilla_flow_views, puis PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS",
                          str(ctx.exception))

    def test_pas_d_indice_quand_un_mot_de_passe_est_fourni(self):
        if db.psycopg is None:
            self.skipTest("psycopg absent")
        with self.assertRaises(db.ErreurBase) as ctx:
            db.connect("postgresql://postgres@127.0.0.1:1/pmzilla", password="MotDePasseInvente-1", timeout=2)
        self.assertNotIn("Aucun mot de passe trouvé", str(ctx.exception))


class CommandeRolePassword(unittest.TestCase):
    def lancer(self, saisies, role="pmzilla_flow_views", definir=None):
        """Pilote main(["role-password", role]) avec un faux getpass et une fausse connexion ; rend (code, sortie, erreur, appels)."""
        conn = unittest.mock.MagicMock()
        sortie, erreur = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(db.getpass, "getpass", side_effect=saisies) as invites, \
                unittest.mock.patch.object(db, "connect", return_value=conn) as connexion, \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            if definir is None:
                code = db.main(["role-password", role])
            else:
                with unittest.mock.patch.object(db, "definir_mot_de_passe", definir):
                    code = db.main(["role-password", role])
        return code, sortie.getvalue(), erreur.getvalue(), invites, connexion, conn

    def test_double_saisie_masquee(self):
        definir = unittest.mock.Mock()
        code, _, _, invites, _, _ = self.lancer(["MotDePasseInvente-12", "MotDePasseInvente-12"], definir=definir)
        self.assertEqual(code, 0)
        self.assertEqual(invites.call_count, 2)                       # getpass : saisie masquée, jamais input()
        self.assertIn("pmzilla_flow_views", invites.call_args_list[0].args[0])

    def test_deux_saisies_differentes(self):
        definir = unittest.mock.Mock()
        code, sortie, erreur, _, connexion, _ = self.lancer(["MotDePasseInvente-12", "AutreMotDePasse-345"], definir=definir)
        self.assertEqual(code, 1)
        self.assertIn("Les deux saisies diffèrent", erreur)
        connexion.assert_not_called()                                 # aucune connexion, aucun mot de passe posé
        definir.assert_not_called()
        self.assertNotIn("security add-generic-password", sortie)

    def test_mot_de_passe_trop_court(self):
        code, sortie, erreur, _, _, conn = self.lancer(["court", "court"])
        self.assertEqual(code, 1)
        self.assertIn("Mot de passe trop court (12 caractères au moins)", erreur)
        self.assertNotIn("court\n", sortie + erreur.replace("trop court", ""))
        conn.execute.assert_not_called()
        conn.close.assert_called_once()                               # connexion fermée malgré l'erreur
        self.assertNotIn("security add-generic-password", sortie)

    def test_mot_de_passe_valide_affiche_la_commande_du_trousseau_sans_le_mot_de_passe(self):
        secret = "MotDePasseInvente-12"
        definir = unittest.mock.Mock()
        code, sortie, erreur, _, _, conn = self.lancer([secret, secret], role="pmzilla_cases", definir=definir)
        self.assertEqual(code, 0)
        definir.assert_called_once_with(conn, "pmzilla_cases", secret)
        conn.close.assert_called_once()
        self.assertIn("Mot de passe posé", sortie)
        self.assertIn('security add-generic-password -U -s pmzilla-lab-db-pmzilla_cases -a "$USER" -w', sortie)
        self.assertNotIn(secret, sortie + erreur)

    def test_role_hors_liste_refuse_par_l_analyseur(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            db.main(["role-password", "postgres"])


if __name__ == "__main__":
    unittest.main()
