"""
Tests du marqueur du jeu synthétique (change mothra-slices, tâche 16.2, design D17 et D34) : le chargeur crée `flow.synthetic_dataset_marker()`
dans la base jetable qu'il charge, sans argument, rend 1, EXECUTE au seul rôle des vues de flow ; aucune migration ne le crée, donc la vraie
base ne le détient jamais et une base sans marqueur est réelle. Aucun de ces tests ne demande une base.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
import jeu_synthetique as jeu  # noqa: E402
from test_chargeur import FausseConnexion  # noqa: E402

MARQUEUR = "synthetic_dataset_marker"
ROLE_DES_VUES = "pmzilla_flow_views"


class ConnexionAuxRoles(FausseConnexion):
    """Répond à SELECT current_user par le dernier rôle pris (SET LOCAL ROLE), comme une vraie session."""

    def __init__(self, **options):
        super().__init__(**options)
        self.role = "postgres"

    def execute(self, sql, params=None):
        texte = " ".join(sql.split())
        trouve = re.match(r"SET LOCAL ROLE (\w+)$", texte)
        if trouve:
            self.role = trouve.group(1)
        return super().execute(sql, params)

    def fetchone(self):
        if "current_user" in self._derniere:
            return (self.role,)
        return super().fetchone()


def ddl(conn) -> list[str]:
    return [sql for sql in conn.instructions if re.match(r"(CREATE|REVOKE|GRANT|ALTER|DROP)\b", sql)]


class MarqueurPose(unittest.TestCase):
    def poser(self, **options) -> ConnexionAuxRoles:
        conn = ConnexionAuxRoles(**options)
        jeu.poser_marqueur(conn)
        return conn

    def test_le_marqueur_est_une_fonction_sans_argument_qui_rend_1(self):
        creation = [s for s in ddl(self.poser()) if s.startswith("CREATE")]
        self.assertEqual(len(creation), 1)
        self.assertRegex(creation[0], rf"^CREATE OR REPLACE FUNCTION flow\.{MARQUEUR}\(\) RETURNS integer\b")
        self.assertRegex(creation[0], r"SELECT 1\b")

    def test_execute_au_seul_role_des_vues_de_flow(self):
        instructions = ddl(self.poser())
        self.assertIn(f"REVOKE ALL ON FUNCTION flow.{MARQUEUR}() FROM PUBLIC", instructions)
        grants = [s for s in instructions if s.startswith("GRANT")]
        self.assertEqual(grants, [f"GRANT EXECUTE ON FUNCTION flow.{MARQUEUR}() TO {ROLE_DES_VUES}"])

    def test_tout_se_passe_en_une_transaction_sous_le_proprietaire_verifie_avant_d_ecrire(self):
        instructions = self.poser().instructions
        self.assertEqual(instructions[:2], ["BEGIN", "SET LOCAL ROLE pmzilla_owner"])
        self.assertEqual(instructions[-1], "COMMIT")
        for sql in instructions:
            if "ROLE" in sql:
                self.assertEqual(sql, "SET LOCAL ROLE pmzilla_owner")
            self.assertNotRegex(sql, r"\b(quality|cases|knowledge|public)\.")

    def test_le_marqueur_ne_lit_ni_n_ecrit_aucune_table(self):
        for sql in self.poser().instructions:
            self.assertNotRegex(sql, r"^(INSERT|UPDATE|DELETE|SELECT)\b", sql)

    def test_connexion_en_autocommit_ou_en_transaction_refusee_avant_toute_instruction(self):
        conn = ConnexionAuxRoles(autocommit=True)
        with self.assertRaises(jeu.RefusJeu):
            jeu.poser_marqueur(conn)
        self.assertEqual(conn.instructions, [])
        conn = ConnexionAuxRoles()
        conn.info = type("Info", (), {"transaction_status": 2})()
        with self.assertRaises(jeu.RefusJeu):
            jeu.poser_marqueur(conn)
        self.assertEqual(conn.instructions, [])

    def test_un_role_non_pris_annule_la_transaction_sans_creation(self):
        conn = ConnexionAuxRoles()
        base = conn.execute

        def refuse(sql, params=None):
            if sql.startswith("SET LOCAL ROLE"):
                base(sql, params)
                raise RuntimeError("role refusé")
            return base(sql, params)

        conn.execute = refuse
        with self.assertRaises(RuntimeError):
            jeu.poser_marqueur(conn)
        self.assertEqual(ddl(conn), [])
        self.assertEqual(conn.instructions[-1], "ROLLBACK")


class MarqueurDansLeChargement(unittest.TestCase):
    ENV = {"DBTEST_PORT": "55432", "PMZILLA_LAB_DB_PORT": "55432", "PMZILLA_LAB_DB_PASSWORD": "x"}

    def test_main_pose_le_marqueur_apres_le_chargement_sur_la_meme_connexion(self):
        conn = ConnexionAuxRoles()
        ouvertures = []

        def connecteur(*args, **kwargs):
            ouvertures.append(kwargs)
            return conn

        with contextlib.redirect_stdout(io.StringIO()):
            code = jeu.main([], env=self.ENV, connecter=connecteur)
        self.assertEqual(code, 0)
        self.assertEqual(len(ouvertures), 2)                       # une sonde de la garde, puis la connexion du chargement : inchangé
        instructions = conn.instructions
        creation = next(i for i, s in enumerate(instructions) if s.startswith("CREATE OR REPLACE FUNCTION"))
        derniere_ecriture = max(i for i, s in enumerate(instructions) if re.match(r"INSERT INTO flow\.", s))
        self.assertGreater(creation, derniere_ecriture)

    def test_un_chargement_refuse_ne_pose_pas_de_marqueur(self):
        conn = ConnexionAuxRoles(cles_reelles=3)
        with contextlib.redirect_stderr(io.StringIO()):
            code = jeu.main([], env=self.ENV, connecter=lambda *a, **k: conn)
        self.assertEqual(code, 2)
        self.assertEqual(ddl(conn), [])


class AucuneMigrationNeCreeLeMarqueur(unittest.TestCase):
    """Test statique (design D17, D34) : le marqueur ne vit que dans le chargeur ; la vraie base ne le détient jamais."""

    def test_aucune_migration_ne_le_nomme(self):
        fichiers = sorted((RACINE / "db" / "migrations").glob("*.sql"))
        self.assertTrue(fichiers)
        for fichier in fichiers:
            self.assertNotIn(MARQUEUR, fichier.read_text(encoding="utf-8"), fichier.name)

    def test_le_chargeur_est_le_seul_a_le_creer(self):
        self.assertIn(f"flow.{MARQUEUR}()", (DOSSIER / "jeu_synthetique.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
