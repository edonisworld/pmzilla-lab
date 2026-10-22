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
import secrets
import stat
import tempfile
import unittest
import unittest.mock
from pathlib import Path

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


FAUX_COFFRE = """#!/bin/sh
# Faux Trousseau d'un fichier : `-i` lit la commande d'ajout sur l'entrée standard (mot de passe = dernier mot) ;
# find-generic-password rend le contenu, sauf pour l'entrée du superutilisateur (absente : sa variable sert).
if [ "$1" = "-i" ]; then
  read -r ligne
  printf '%s\\n' "${ligne##* }" > "$FAUX_COFFRE"
  exit 0
fi
[ "$1" = "find-generic-password" ] && [ "$3" != "pmzilla-lab-db" ] && [ -s "$FAUX_COFFRE" ] && cat "$FAUX_COFFRE" && exit 0
exit 44
"""


class RolePasswordBaseJetable(BaseJetable):
    """Tâche 1.4 : sur une base jetable seulement (sautée sans elle, lancée par l'auteur)."""

    def test_le_mot_de_passe_genere_permet_la_connexion_par_le_faux_trousseau(self):
        role = "pmzilla_test_" + secrets.token_hex(4)

        def retirer():          # la base d'abord (elle porte les droits du rôle), puis le rôle
            self._supprimer()
            with db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True) as nettoyage:
                nettoyage.execute(f'DROP ROLE IF EXISTS "{role}"')
        self.addCleanup(retirer)
        self.admin.execute(f'CREATE ROLE "{role}" NOLOGIN')
        self.admin.execute(f'GRANT CONNECT ON DATABASE "{self.nom_base}" TO "{role}"')
        with tempfile.TemporaryDirectory() as dossier:
            dossier = Path(dossier)
            double = dossier / "security"
            double.write_text(FAUX_COFFRE)
            double.chmod(double.stat().st_mode | stat.S_IXUSR)
            env = {db.VARIABLE_URL: self.url, db.VARIABLE_SECURITY: str(double), db.VARIABLE_MOT_DE_PASSE: base.MOT_DE_PASSE,
                   "FAUX_COFFRE": str(dossier / "coffre")}
            with unittest.mock.patch.dict(os.environ, env), \
                    unittest.mock.patch.object(db, "ROLES_AVEC_MOT_DE_PASSE", (role,)):
                db.generer_poser_ranger(role, (role,))
                rangé = (dossier / "coffre").read_text().strip()
                self.assertGreater(len(rangé), 12)
                limite = db.connect(self.url, role=role)               # mot de passe relu dans le faux Trousseau
                self.ouvertes.append(limite)
                self.assertEqual(limite.execute("SELECT current_user").fetchone()[0], role)
            verifieur = self.admin.execute("SELECT rolpassword FROM pg_authid WHERE rolname = %s", (role,)).fetchone()[0]
            self.assertTrue(verifieur.startswith("SCRAM-SHA-256$"))
            self.assertNotIn(rangé, verifieur)


class SansBase(unittest.TestCase):
    def test_migration_0003_ajoute_la_colonne_sans_donnee(self):
        texte = (db.DOSSIER_MIGRATIONS / "0003_flow_has_history.sql").read_text(encoding="utf-8")
        sql = "\n".join(l.split("--")[0] for l in texte.splitlines())
        self.assertRegex(sql, r"(?i)ALTER TABLE flow\.issues ADD COLUMN has_history boolean NOT NULL DEFAULT false")
        self.assertNotRegex(sql, r"(?i)\bINSERT\s+INTO")

    def test_indice_sans_mot_de_passe_nomme_le_trousseau_et_la_variable(self):
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
        with self.assertRaises(db.ErreurBase) as ctx:
            db.connect("postgresql://postgres@127.0.0.1:1/pmzilla", password="MotDePasseInvente-1", timeout=2)
        self.assertNotIn("Aucun mot de passe trouvé", str(ctx.exception))


FAUX_TROUSSEAU = """#!/bin/sh
printf '%s\\n' "$@" > "$FAUX_TROUSSEAU_ARGS"
cat > "$FAUX_TROUSSEAU_ENTREE"
exit "${FAUX_TROUSSEAU_CODE:-0}"
"""
VERIFIEUR = "SCRAM-SHA-256$4096:c2VsSW52ZW50ZQ==$Y2xlU3RvY2tlZQ==:Y2xlU2VydmV1cg=="


class FausseConnexion:
    """Fausse connexion de superutilisateur : enregistre dans `evenements` les instructions et les appels de transaction."""
    def __init__(self, evenements, echec_verifieur=False):
        self.evenements = evenements
        self.instructions = []
        self.pgconn = unittest.mock.MagicMock()
        if echec_verifieur:
            self.pgconn.encrypt_password.side_effect = RuntimeError("pas de chiffrement")
        else:
            self.pgconn.encrypt_password.return_value = VERIFIEUR.encode()

    def execute(self, requete, params=None):
        texte = requete if isinstance(requete, str) else requete.as_string(None)
        self.instructions.append(texte)
        self.evenements.append("execute")
        return unittest.mock.MagicMock()

    def commit(self):
        self.evenements.append("commit")

    def rollback(self):
        self.evenements.append("rollback")

    def close(self):
        self.evenements.append("close")


class FausseSession:
    """Session d'essai sous le rôle : répond `SELECT current_user`."""
    def __init__(self, utilisateur):
        self.utilisateur = utilisateur
        self.fermee = False

    def execute(self, requete, params=None):
        resultat = unittest.mock.MagicMock()
        resultat.fetchone.return_value = (self.utilisateur,)
        return resultat

    def close(self):
        self.fermee = True


class CommandeRolePassword(unittest.TestCase):
    ROLE = "pmzilla_flow_views"

    def setUp(self):
        self.evenements = []
        self.mots_de_passe_rangés = []

    def lancer(self, role=None, *, echec_verifieur=False, refus_trousseau=False, session=None, erreur_session=None,
               relecture="identique", variable="aucune"):
        """Pilote main(["role-password", role]) : fausse connexion, Trousseau doublé, session d'essai doublée, getpass interdit.
        `relecture` : "identique" (rend le mot de passe rangé), "differente", "echec" (rien) ou "exception" (la relecture lève).
        `variable` : la variable d'environnement du mot de passe du rôle, posée pendant la commande : "aucune", "rangee" (elle
        porte le mot de passe généré, comme une copie à jour) ou "autre" (elle porte une valeur étrangère).
        Rend (code, sortie, erreur, connexion superutilisateur)."""
        role = role or self.ROLE
        superutilisateur = FausseConnexion(self.evenements, echec_verifieur)
        self.appels_relecture = []

        def ranger(r, mot_de_passe, security=None):
            self.evenements.append("trousseau")
            self.mots_de_passe_rangés.append(mot_de_passe)
            if variable == "rangee":
                os.environ[db.variable_du_role(role)] = mot_de_passe
            if refus_trousseau:
                raise db.ErreurBase(f"le Trousseau a refusé l'écriture (service {db.service_du_role(r)}) ; "
                                    "aucun mot de passe n'a été posé.")

        def relire(security=None, role=None):
            self.evenements.append("relecture")
            self.appels_relecture.append(role)
            if relecture == "exception":
                raise db.ErreurBase(f"relecture en échec : {self.mots_de_passe_rangés[-1]}")   # un faux message qui porterait le secret
            return {"identique": lambda: self.mots_de_passe_rangés[-1], "differente": lambda: "Autre-Valeur-0123456789",
                    "echec": lambda: None}[relecture]()

        def connecter(*args, **kwargs):
            if kwargs.get("role"):
                self.evenements.append("session")
                if erreur_session:
                    raise db.ErreurBase(erreur_session)
                return session or FausseSession(kwargs["role"])
            return superutilisateur

        sortie, erreur = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(db.getpass, "getpass", side_effect=AssertionError("aucune saisie attendue")), \
                unittest.mock.patch("builtins.input", side_effect=AssertionError("aucune saisie attendue")), \
                unittest.mock.patch.object(db, "ranger_dans_trousseau", ranger), \
                unittest.mock.patch.object(db, "mot_de_passe_trousseau", relire), \
                unittest.mock.patch.object(db, "connect", connecter), \
                unittest.mock.patch.dict(os.environ), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            if variable == "autre":
                os.environ[db.variable_du_role(role)] = "Variable-Etrangere-0123456789"
            code = db.main(["role-password", role])
        return code, sortie.getvalue(), erreur.getvalue(), superutilisateur

    def test_aucune_saisie_et_succes(self):
        code, sortie, erreur, _ = self.lancer()
        self.assertEqual(code, 0)                                      # getpass et input() lèvent s'ils sont appelés
        self.assertIn(f"Mot de passe de {self.ROLE} généré, posé et rangé dans le Trousseau "
                      f"(service pmzilla-lab-db-{self.ROLE}) ; connexion d'essai réussie.", sortie)
        secret = self.mots_de_passe_rangés[0]
        self.assertNotIn(secret, sortie + erreur)

    def test_deux_executions_donnent_deux_mots_de_passe_differents_de_l_alphabet(self):
        for _ in range(2):
            self.assertEqual(self.lancer()[0], 0)
        premier, second = self.mots_de_passe_rangés
        self.assertNotEqual(premier, second)
        for mot in (premier, second):
            self.assertGreater(len(mot), 12)                           # au-dessus du minimum du poseur
            self.assertRegex(mot, r"^[A-Za-z0-9][A-Za-z0-9_-]*$")      # lettres, chiffres, tiret, tiret bas

    def test_ordre_transaction_trousseau_validation_session(self):
        code, _, _, _ = self.lancer()
        self.assertEqual(code, 0)
        self.assertEqual(self.evenements, ["execute", "trousseau", "relecture", "commit", "close", "session"])

    PHRASE_RELECTURE = "Erreur : le Trousseau n'a pas rendu le mot de passe écrit (service pmzilla-lab-db-{role}) ; aucun mot de passe n'a été posé."

    def test_entree_relue_et_comparee_avant_la_validation(self):
        for relecture in ("differente", "echec", "exception"):
            with self.subTest(relecture=relecture):
                self.evenements.clear()
                self.mots_de_passe_rangés.clear()
                code, sortie, erreur, _ = self.lancer(relecture=relecture)
                secret = self.mots_de_passe_rangés[0]
                self.assertEqual(code, 1)
                self.assertIn(self.PHRASE_RELECTURE.format(role=self.ROLE), erreur)
                self.assertIn("rollback", self.evenements)
                self.assertNotIn("commit", self.evenements)
                self.assertNotIn("session", self.evenements)
                self.assertNotIn(secret, sortie + erreur)               # ni le cas de différence, ni l'échec de relecture
                self.assertNotIn("Autre-Valeur-0123456789", sortie + erreur)

    def test_relecture_lit_le_trousseau_meme_quand_la_variable_d_environnement_est_posee(self):
        """Une relecture qui retomberait sur la variable (lire_mot_de_passe, os.environ) validerait un Trousseau vide ou périmé."""
        # variable à jour, Trousseau qui ne rend rien : seul le Trousseau compte, la validation est refusée
        for relecture in ("echec", "differente"):
            with self.subTest(relecture=relecture):
                self.evenements.clear()
                self.mots_de_passe_rangés.clear()
                code, sortie, erreur, _ = self.lancer(relecture=relecture, variable="rangee")
                self.assertEqual(code, 1)
                self.assertIn(self.PHRASE_RELECTURE.format(role=self.ROLE), erreur)
                self.assertIn("relecture", self.evenements)            # la lecture du Trousseau a été appelée
                self.assertNotIn("commit", self.evenements)
                self.assertNotIn(self.mots_de_passe_rangés[0], sortie + erreur)
        # variable étrangère, Trousseau à jour : la variable ne fait pas échouer la relecture
        self.evenements.clear()
        self.mots_de_passe_rangés.clear()
        code, _, _, _ = self.lancer(relecture="identique", variable="autre")
        self.assertEqual(code, 0)
        self.assertEqual(self.appels_relecture, [self.ROLE])           # le Trousseau du rôle, pas celui du superutilisateur

    def test_refus_d_ecriture_dans_le_trousseau_aucune_relecture(self):
        for relecture in ("identique", "differente", "echec"):
            with self.subTest(relecture=relecture):
                self.evenements.clear()
                self.mots_de_passe_rangés.clear()
                code, sortie, erreur, _ = self.lancer(refus_trousseau=True, relecture=relecture, variable="rangee")
                self.assertEqual(code, 1)
                self.assertNotIn("relecture", self.evenements)         # rien à relire : l'écriture a été refusée
                self.assertEqual(self.appels_relecture, [])
                self.assertEqual(self.evenements[:3], ["execute", "trousseau", "rollback"])
                self.assertNotIn("commit", self.evenements)
                self.assertNotIn("session", self.evenements)
                self.assertNotIn(self.mots_de_passe_rangés[0], sortie + erreur)
                self.assertIn("a refusé l'écriture", erreur)           # et non la phrase de la relecture
                self.assertNotIn("n'a pas rendu", erreur)

    def test_relecture_par_la_recherche_normale_du_trousseau(self):
        """La vraie fonction de relecture est celle de la recherche normale : find-generic-password avec le service du rôle."""
        with tempfile.TemporaryDirectory() as dossier:
            double = Path(dossier) / "security"
            double.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$FAUX_TROUSSEAU_ARGS\"\necho SecretRelu-0123456789\n")
            double.chmod(double.stat().st_mode | stat.S_IXUSR)
            with unittest.mock.patch.dict(os.environ, {"FAUX_TROUSSEAU_ARGS": str(Path(dossier) / "args")}):
                self.assertEqual(db.mot_de_passe_trousseau(str(double), self.ROLE), "SecretRelu-0123456789")
            arguments = (Path(dossier) / "args").read_text().split()
        self.assertIn("find-generic-password", arguments)
        self.assertIn(f"pmzilla-lab-db-{self.ROLE}", arguments)

    def test_la_requete_porte_un_verifieur_jamais_le_mot_de_passe_en_clair(self):
        _, sortie, erreur, conn = self.lancer()
        secret = self.mots_de_passe_rangés[0]
        self.assertEqual(len(conn.instructions), 1)
        self.assertIn(VERIFIEUR, conn.instructions[0])
        self.assertIn("ALTER ROLE", conn.instructions[0])
        self.assertNotIn(secret, conn.instructions[0])
        conn.pgconn.encrypt_password.assert_called_once()
        self.assertEqual(conn.pgconn.encrypt_password.call_args.args[0], secret.encode())
        self.assertEqual(conn.pgconn.encrypt_password.call_args.args[2], b"scram-sha-256")

    def test_trousseau_refuse_annule_et_ne_valide_pas(self):
        code, sortie, erreur, _ = self.lancer(refus_trousseau=True)
        self.assertEqual(code, 1)
        self.assertIn(f"Erreur : le Trousseau a refusé l'écriture (service pmzilla-lab-db-{self.ROLE}) ; "
                      "aucun mot de passe n'a été posé.", erreur)
        self.assertIn("rollback", self.evenements)
        self.assertNotIn("commit", self.evenements)
        self.assertNotIn("session", self.evenements)
        self.assertNotIn(self.mots_de_passe_rangés[0], sortie + erreur)

    def test_echec_de_la_session_d_essai(self):
        message = "Connexion à la base impossible : mot de passe refusé."
        code, sortie, erreur, _ = self.lancer(erreur_session=message)
        self.assertEqual(code, 1)
        self.assertIn(f"Erreur : mot de passe posé et rangé, mais la connexion d'essai sous {self.ROLE} a échoué : "
                      f"{message}", erreur)
        self.assertIn("commit", self.evenements)                       # posé et rangé : la validation a eu lieu
        self.assertNotIn(self.mots_de_passe_rangés[0], sortie + erreur)

    def test_session_d_essai_sous_un_autre_utilisateur_est_un_echec(self):
        code, _, erreur, _ = self.lancer(session=FausseSession("postgres"))
        self.assertEqual(code, 1)
        self.assertIn("la connexion d'essai sous", erreur)

    def test_verifieur_impossible_a_calculer_ne_modifie_rien(self):
        code, sortie, erreur, conn = self.lancer(echec_verifieur=True)
        self.assertEqual(code, 1)
        self.assertIn("Erreur : chiffrement du mot de passe impossible côté client ; rien n'a été modifié.", erreur)
        self.assertEqual(conn.instructions, [])
        self.assertNotIn("trousseau", self.evenements)
        self.assertNotIn("commit", self.evenements)

    def test_trousseau_recoit_le_mot_de_passe_sur_l_entree_standard_et_dans_aucun_argument(self):
        with tempfile.TemporaryDirectory() as dossier:
            dossier = Path(dossier)
            double = dossier / "security"
            double.write_text(FAUX_TROUSSEAU)
            double.chmod(double.stat().st_mode | stat.S_IXUSR)
            env = {"FAUX_TROUSSEAU_ARGS": str(dossier / "args"), "FAUX_TROUSSEAU_ENTREE": str(dossier / "entree")}
            with unittest.mock.patch.dict(os.environ, env):
                db.ranger_dans_trousseau(self.ROLE, "SecretInvente-ABCdef_12345", security=str(double))
            arguments = (dossier / "args").read_text()
            entree = (dossier / "entree").read_text()
        self.assertNotIn("SecretInvente-ABCdef_12345", arguments)
        self.assertIn("-i", arguments.split())                         # mode interactif
        self.assertIn("add-generic-password", entree)
        self.assertIn(f"-s pmzilla-lab-db-{self.ROLE}", entree)
        self.assertIn("-U", entree)                                    # remplace une entrée existante
        self.assertIn("SecretInvente-ABCdef_12345", entree)

    def test_trousseau_en_echec_leve_sans_le_mot_de_passe(self):
        with tempfile.TemporaryDirectory() as dossier:
            dossier = Path(dossier)
            double = dossier / "security"
            double.write_text(FAUX_TROUSSEAU)
            double.chmod(double.stat().st_mode | stat.S_IXUSR)
            env = {"FAUX_TROUSSEAU_ARGS": str(dossier / "args"), "FAUX_TROUSSEAU_ENTREE": str(dossier / "entree"),
                   "FAUX_TROUSSEAU_CODE": "45"}
            with unittest.mock.patch.dict(os.environ, env):
                with self.assertRaises(db.ErreurBase) as ctx:
                    db.ranger_dans_trousseau(self.ROLE, "SecretInvente-ABCdef_12345", security=str(double))
        self.assertEqual(f"le Trousseau a refusé l'écriture (service pmzilla-lab-db-{self.ROLE}) ; aucun mot de passe n'a été posé.",
                         str(ctx.exception))                           # phrase de D6 rendue par la vraie fonction
        self.assertNotIn("SecretInvente-ABCdef_12345", str(ctx.exception))
        with self.assertRaises(db.ErreurBase):                         # commande introuvable : même refus
            db.ranger_dans_trousseau(self.ROLE, "SecretInvente-ABCdef_12345", security="/inexistant/security")

    def test_mot_de_passe_trop_court_au_niveau_du_poseur(self):
        with self.assertRaises(db.ErreurBase) as ctx:
            db.definir_mot_de_passe(FausseConnexion([]), self.ROLE, "court")
        self.assertIn("Mot de passe trop court (12 caractères au moins)", str(ctx.exception))

    def test_role_hors_liste_refuse_par_l_analyseur(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            db.main(["role-password", "postgres"])

    def test_role_des_vues_de_qualite_accepte_et_ses_deux_autres_roles_refuses(self):
        """R-78 (spec database-roles-views, « Limited roles log in… ») : seul le rôle des vues du schéma quality reçoit un mot de passe."""
        secret = "MotDePasseInvente-12"
        code, sortie, erreur, _ = self.lancer(role="pmzilla_quality_views")
        self.assertEqual(code, 0)
        self.assertIn("(service pmzilla-lab-db-pmzilla_quality_views)", sortie)
        self.assertNotIn(self.mots_de_passe_rangés[0], sortie + erreur)
        for refuse in ("pmzilla_quality", "pmzilla_quality_ro"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                db.main(["role-password", refuse])
            with self.assertRaises(db.ErreurBase):                       # et le setter lui-même refuse, avant toute connexion
                db.definir_mot_de_passe(unittest.mock.Mock(), refuse, secret)
            with self.assertRaises(db.ErreurBase):
                db.connect("postgresql://postgres@127.0.0.1:1/x", password=secret, role=refuse)

    def test_secret_propre_au_role_des_vues_de_qualite(self):
        self.assertEqual(db.service_du_role("pmzilla_quality_views"), "pmzilla-lab-db-pmzilla_quality_views")
        self.assertEqual(db.variable_du_role("pmzilla_quality_views"), "PMZILLA_LAB_DB_PASSWORD_PMZILLA_QUALITY_VIEWS")
        for autre in ("pmzilla_flow_views", "pmzilla_cases", "pmzilla_cases_ro", "pmzilla_knowledge_ro"):
            self.assertNotEqual(db.service_du_role("pmzilla_quality_views"), db.service_du_role(autre))
            self.assertNotEqual(db.variable_du_role("pmzilla_quality_views"), db.variable_du_role(autre))
        self.assertNotEqual(db.service_du_role("pmzilla_quality_views"), db.SERVICE_TROUSSEAU)


if __name__ == "__main__":
    unittest.main()
