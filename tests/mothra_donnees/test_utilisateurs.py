"""
Tests des utilisateurs synthétiques de l'e2e (change mothra-slices, tâche 20.1, R-20261102-65 (1) et -66 (1)) : le chargeur écrit deux
utilisateurs de mothra.users, un auteur et un relecteur, sous le rôle de stockage de Mothra, dans une transaction à part, sans DDL.
Aucun de ces tests ne demande une base.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import unittest
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
import jeu_synthetique as jeu  # noqa: E402
from test_chargeur import FausseConnexion  # noqa: E402

MOTIF_IDENTIFIANT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")   # mothra.users.id (migration 0024)


class ConnexionAvecParametres(FausseConnexion):
    """Garde aussi les paramètres de chaque instruction."""

    def __init__(self, **options):
        super().__init__(**options)
        self.parametres: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.parametres.append((" ".join(sql.split()), params))
        return super().execute(sql, params)


class UtilisateursSynthetiques(unittest.TestCase):
    def poser(self) -> ConnexionAvecParametres:
        conn = ConnexionAvecParametres()
        jeu.poser_utilisateurs(conn)
        return conn

    def test_deux_utilisateurs_un_auteur_et_un_relecteur_aux_identifiants_de_role(self):
        self.assertEqual(sorted(role for _, role in jeu.UTILISATEURS_SYNTHETIQUES), ["author", "reviewer"])
        for identifiant, _ in jeu.UTILISATEURS_SYNTHETIQUES:
            self.assertRegex(identifiant, MOTIF_IDENTIFIANT)
        self.assertEqual([i for i, _ in jeu.UTILISATEURS_SYNTHETIQUES], ["author-synth", "reviewer-synth"])

    def test_une_transaction_a_part_sous_le_role_de_stockage_puis_deux_insertions(self):
        conn = self.poser()
        self.assertEqual(conn.instructions[:2], ["BEGIN", "SET LOCAL ROLE pmzilla_mothra"])
        self.assertEqual(conn.instructions[-1], "COMMIT")
        insertions = [sql for sql in conn.instructions if sql.startswith("INSERT")]
        self.assertEqual(len(insertions), 2)
        for sql in insertions:
            self.assertRegex(sql, r"^INSERT INTO mothra\.users \(id, role\) VALUES \(%s, %s\) ON CONFLICT \(id\) DO NOTHING$")
        ecrits = [params for sql, params in conn.parametres if sql.startswith("INSERT")]
        self.assertEqual(ecrits, [tuple(u) for u in jeu.UTILISATEURS_SYNTHETIQUES])

    def test_aucun_autre_role_aucun_ddl_aucun_autre_schema(self):
        for sql in self.poser().instructions:
            if "ROLE" in sql:
                self.assertEqual(sql, "SET LOCAL ROLE pmzilla_mothra")
            self.assertNotRegex(sql, r"^(CREATE|ALTER|DROP|GRANT|REVOKE|DELETE|UPDATE)\b")
            self.assertNotRegex(sql, r"\b(flow|quality|cases|knowledge|public)\.")

    def test_connexion_en_autocommit_ou_en_transaction_refusee_avant_toute_instruction(self):
        conn = ConnexionAvecParametres(autocommit=True)
        with self.assertRaises(jeu.RefusJeu):
            jeu.poser_utilisateurs(conn)
        self.assertEqual(conn.instructions, [])
        conn = ConnexionAvecParametres()
        conn.info = type("Info", (), {"transaction_status": 2})()
        with self.assertRaises(jeu.RefusJeu):
            jeu.poser_utilisateurs(conn)
        self.assertEqual(conn.instructions, [])

    def test_un_role_non_pris_annule_la_transaction_sans_insertion(self):
        conn = ConnexionAvecParametres()
        base = conn.execute

        def refuse(sql, params=None):
            if sql.startswith("SET LOCAL ROLE"):
                base(sql, params)
                raise RuntimeError("role refusé")
            return base(sql, params)

        conn.execute = refuse
        with self.assertRaises(RuntimeError):
            jeu.poser_utilisateurs(conn)
        self.assertEqual([s for s in conn.instructions if s.startswith("INSERT")], [])
        self.assertEqual(conn.instructions[-1], "ROLLBACK")


class UtilisateursDansLeChargement(unittest.TestCase):
    ENV = {"DBTEST_PORT": "55432", "PMZILLA_LAB_DB_PORT": "55432", "PMZILLA_LAB_DB_PASSWORD": "x"}

    def test_main_les_pose_apres_le_marqueur_sur_la_meme_connexion(self):
        conn = ConnexionAvecParametres()
        with contextlib.redirect_stdout(io.StringIO()):
            code = jeu.main([], env=self.ENV, connecter=lambda *a, **k: conn)
        self.assertEqual(code, 0)
        instructions = conn.instructions
        marqueur = next(i for i, s in enumerate(instructions) if s.startswith("CREATE OR REPLACE FUNCTION"))
        utilisateurs = [i for i, s in enumerate(instructions) if s.startswith("INSERT INTO mothra.users")]
        self.assertEqual(len(utilisateurs), 2)
        self.assertGreater(min(utilisateurs), marqueur)
        # entre le marqueur et la première insertion : la validation du marqueur, puis la transaction à part des utilisateurs
        premiere = min(utilisateurs)
        self.assertEqual(instructions[premiere - 3:premiere], ["COMMIT", "BEGIN", "SET LOCAL ROLE pmzilla_mothra"])

    def test_un_chargement_refuse_ne_pose_aucun_utilisateur(self):
        conn = ConnexionAvecParametres(cles_reelles=3)
        with contextlib.redirect_stderr(io.StringIO()):
            code = jeu.main([], env=self.ENV, connecter=lambda *a, **k: conn)
        self.assertEqual(code, 2)
        self.assertEqual([s for s in conn.instructions if "mothra.users" in s], [])


if __name__ == "__main__":
    unittest.main()
