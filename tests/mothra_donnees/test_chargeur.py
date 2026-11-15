"""
Tests du chargeur du jeu synthétique de Mothra (#240, tâche 5.1) : refus sans base jetable, écritures sous le rôle d'import,
aucune lecture de fichier du dossier de flux. Aucun de ces tests ne demande une base.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import ast
import contextlib
import io
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
import jeu_synthetique as jeu  # noqa: E402

SCRIPT = DOSSIER / "jeu_synthetique.py"
MESSAGE = "jeu synthétique : base jetable absente"


def env_sans_base() -> dict[str, str]:
    """Environnement d'un sous-processus : aucune variable de base, aucun repère de base jetable."""
    return {c: v for c, v in os.environ.items() if not c.startswith("PMZILLA_LAB_DB_") and c != "DBTEST_PORT"}


class ConnexionInterdite:
    """Connecteur qui échoue si on l'appelle : prouve qu'aucune connexion n'est ouverte."""

    def __init__(self):
        self.appels = 0

    def __call__(self, *args, **kwargs):
        self.appels += 1
        raise AssertionError("connexion ouverte alors que la base jetable est absente")


class RefusSansBase(unittest.TestCase):
    def test_sans_repere_sortie_2_message_aucune_connexion(self):
        connecteur = ConnexionInterdite()
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur):
            code = jeu.main([], env={}, connecter=connecteur)
        self.assertEqual(code, 2)
        self.assertIn(MESSAGE, erreur.getvalue())
        self.assertEqual(connecteur.appels, 0)

    def test_repere_vide_ou_illisible_refuse_aussi(self):
        for valeur in ("", "5432", "abc", "05433", "-1", " 55432"):
            with self.subTest(valeur=valeur):
                connecteur = ConnexionInterdite()
                erreur = io.StringIO()
                env = {"DBTEST_PORT": valeur, "PMZILLA_LAB_DB_PORT": valeur, "PMZILLA_LAB_DB_PASSWORD": "x"}
                with contextlib.redirect_stderr(erreur):
                    code = jeu.main([], env=env, connecter=connecteur)
                self.assertEqual(code, 2)
                self.assertIn(MESSAGE, erreur.getvalue())
                self.assertEqual(connecteur.appels, 0)

    def test_port_de_connexion_different_du_repere_refuse(self):
        connecteur = ConnexionInterdite()
        erreur = io.StringIO()
        env = {"DBTEST_PORT": "55432", "PMZILLA_LAB_DB_PORT": "5432", "PMZILLA_LAB_DB_PASSWORD": "x"}
        with contextlib.redirect_stderr(erreur):
            code = jeu.main([], env=env, connecter=connecteur)
        self.assertEqual(code, 2)
        self.assertIn(MESSAGE, erreur.getvalue())
        self.assertEqual(connecteur.appels, 0)

    def test_script_lance_a_nu_sans_repere(self):
        fait = subprocess.run([sys.executable, "-B", "-I", str(SCRIPT)], capture_output=True, text=True, env=env_sans_base(),
                              stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(fait.returncode, 2, fait.stderr)
        self.assertIn(MESSAGE, fait.stderr)


class FausseConnexion:
    """Enregistre chaque instruction dans l'ordre, avec le début et la fin de la transaction ; rend des identifiants d'équipe croissants.

    `utilisateur` : ce que répond SELECT current_user ; `cles_reelles` : le nombre de clés hors SYN-% ; `equipes` : les noms déjà en base."""

    def __init__(self, autocommit=False, utilisateur="pmzilla_flow", cles_reelles=0, equipes=()):
        self.autocommit = autocommit
        self.utilisateur = utilisateur
        self.cles_reelles = cles_reelles
        self.equipes = list(equipes)
        self.instructions: list[str] = []
        self._id = 0
        self._derniere = ""

    def transaction(self):
        conn = self

        class Transaction:
            def __enter__(self):
                conn.instructions.append("BEGIN")
                return self

            def __exit__(self, type_, valeur, trace):
                conn.instructions.append("ROLLBACK" if type_ else "COMMIT")
                return False

        return Transaction()

    def execute(self, sql, params=None):
        self._derniere = " ".join(sql.split())
        self.instructions.append(self._derniere)
        return self

    def fetchone(self):
        if "current_user" in self._derniere:
            return (self.utilisateur,)
        if "count(*)" in self._derniere:
            return (self.cles_reelles,)
        self._id += 1
        return (self._id,)

    def fetchall(self):
        return [(nom,) for nom in self.equipes]

    def close(self):
        pass

    def ecritures(self) -> list[str]:
        return [sql for sql in self.instructions if re.match(r"(INSERT|DELETE|UPDATE)\b", sql)]


class EcrituresSousLeRoleDImport(unittest.TestCase):
    def charger(self) -> list[str]:
        conn = FausseConnexion()
        jeu.charger(conn, jeu.INSTANT_FIXE)
        return conn.instructions

    def test_le_role_est_pris_en_local_dans_la_transaction_puis_verifie(self):
        self.assertEqual(self.charger()[:3], ["BEGIN", "SET LOCAL ROLE pmzilla_flow", "SELECT current_user"])

    def test_aucun_set_role_ni_reset_role_hors_transaction(self):
        for sql in self.charger():
            self.assertNotRegex(sql, r"^(SET ROLE|RESET ROLE)\b", sql)

    def test_toute_ecriture_a_lieu_sous_le_role_et_dans_flow(self):
        role_pris = False
        for sql in self.charger():
            if sql == "SET LOCAL ROLE pmzilla_flow":
                role_pris = True
            elif sql in ("COMMIT", "ROLLBACK"):
                role_pris = False
            elif re.match(r"(INSERT|DELETE|UPDATE)\b", sql):
                self.assertTrue(role_pris, sql)
                self.assertRegex(sql, r"flow\.(issues|teams|issue_teams)\b", sql)

    def test_aucun_autre_role_ni_schema(self):
        for sql in self.charger():
            if "ROLE" in sql:
                self.assertEqual(sql, "SET LOCAL ROLE pmzilla_flow")
            self.assertNotRegex(sql, r"\b(quality|cases|knowledge|public)\.")

    def test_validation_en_dernier(self):
        self.assertEqual(self.charger()[-1], "COMMIT")

    def test_connexion_en_autocommit_refusee_avant_toute_instruction(self):
        conn = FausseConnexion(autocommit=True)
        with self.assertRaises(jeu.RefusJeu):
            jeu.charger(conn, jeu.INSTANT_FIXE)
        self.assertEqual(conn.instructions, [])

    def test_connexion_deja_dans_une_transaction_refusee_avant_toute_instruction(self):
        conn = FausseConnexion()
        conn.info = type("Info", (), {"transaction_status": 2})()   # INTRANS
        with self.assertRaises(jeu.RefusJeu):
            jeu.charger(conn, jeu.INSTANT_FIXE)
        self.assertEqual(conn.instructions, [])

    def test_role_non_pris_refuse_sans_ecriture(self):
        conn = FausseConnexion(utilisateur="postgres")
        with self.assertRaises(jeu.RefusJeu):
            jeu.charger(conn, jeu.INSTANT_FIXE)
        self.assertEqual(conn.ecritures(), [])
        self.assertEqual(conn.instructions[-1], "ROLLBACK")

    def test_cle_reelle_refusee_sans_ecriture(self):
        conn = FausseConnexion(cles_reelles=1)
        with self.assertRaises(jeu.RefusJeu) as refus:
            jeu.charger(conn, jeu.INSTANT_FIXE)
        self.assertEqual(str(refus.exception), MESSAGE)
        self.assertEqual(conn.ecritures(), [])

    def test_nom_d_equipe_hors_du_jeu_refuse_sans_ecriture(self):
        conn = FausseConnexion(equipes=["équipe A", "Nom hors du jeu"])
        with self.assertRaises(jeu.RefusJeu) as refus:
            jeu.charger(conn, jeu.INSTANT_FIXE)
        self.assertEqual(str(refus.exception), MESSAGE)
        self.assertEqual(conn.ecritures(), [])

    def test_equipes_generiques_deja_presentes_acceptees(self):
        conn = FausseConnexion(equipes=sorted(jeu.EQUIPES_GENERIQUES))
        jeu.charger(conn, jeu.INSTANT_FIXE)
        self.assertTrue(conn.ecritures())

    def test_ensemble_generique_egal_aux_equipes_des_groupes(self):
        self.assertEqual(jeu.EQUIPES_GENERIQUES, {g[0] for g in jeu.GROUPES if g[0]})

    def test_main_refuse_une_base_a_donnees_reelles_sortie_2_et_meme_phrase(self):
        conn = FausseConnexion(cles_reelles=3)
        erreur = io.StringIO()
        env = {"DBTEST_PORT": "55432", "PMZILLA_LAB_DB_PORT": "55432", "PMZILLA_LAB_DB_PASSWORD": "x"}
        with contextlib.redirect_stderr(erreur):
            code = jeu.main([], env=env, connecter=lambda *a, **k: conn)
        self.assertEqual(code, 2)
        self.assertIn(MESSAGE, erreur.getvalue())
        self.assertEqual(conn.ecritures(), [])

    def test_deux_ouvertures_apres_la_garde_une_sonde_puis_le_chargement(self):
        ouvertures = []

        def connecteur(*args, **kwargs):
            ouvertures.append(kwargs)
            return FausseConnexion()

        env = {"DBTEST_PORT": "55432", "PMZILLA_LAB_DB_PORT": "55432", "PMZILLA_LAB_DB_PASSWORD": "x"}
        with contextlib.redirect_stdout(io.StringIO()):
            code = jeu.main([], env=env, connecter=connecteur)
        self.assertEqual(code, 0)
        # une sonde de la garde, puis la connexion du chargement
        self.assertEqual(len(ouvertures), 2)
        for kwargs in ouvertures:
            self.assertEqual(kwargs.get("password"), "x")


class AucuneLectureDeFichierDeFlux(unittest.TestCase):
    """Test statique : le chargeur et son jeu ne lisent aucun fichier, et ne nomment aucun fichier du dossier de flux."""

    def setUp(self):
        self.source = SCRIPT.read_text(encoding="utf-8")
        self.arbre = ast.parse(self.source)

    def test_aucun_nom_de_fichier_de_flux(self):
        for nom in ("Flux-Lab", "equipes-lisibles", "equipes-jira", "flux.yaml", "noms-sensibles", "organisation.yaml", "exports", "tableaux"):
            self.assertNotIn(nom, self.source, nom)

    def test_aucune_lecture_de_fichier(self):
        interdits = {"open", "read_text", "read_bytes", "glob", "rglob", "listdir", "scandir", "iterdir", "walk", "load", "safe_load"}
        for noeud in ast.walk(self.arbre):
            if isinstance(noeud, ast.Call):
                f = noeud.func
                nom = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                self.assertNotIn(nom, interdits, f"ligne {noeud.lineno}")

    def test_imports_en_liste_blanche(self):
        autorises = {"os", "sys", "datetime", "pathlib", "__future__", "garde_base_jetable", "referentiel_synthetique"}   # R-20261028-107
        for noeud in ast.walk(self.arbre):
            if isinstance(noeud, ast.Import):
                modules = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                modules = [noeud.module or ""]
            else:
                continue
            for module in modules:
                self.assertIn(module.split(".")[0], autorises, f"ligne {noeud.lineno} : import hors liste blanche : {module}")

    def test_le_referentiel_synthetique_n_importe_que_des_modules_de_la_liste_blanche(self):
        # décision R-20261028-107 : le module admis par la liste blanche ne l'élargit pas ; flow_referential (outil sans entrée-sortie) est sa seule exception
        autorises = {"os", "sys", "datetime", "pathlib", "__future__", "flow_referential"}
        for chemin, permis in ((DOSSIER / "referentiel_synthetique.py", autorises),
                               (RACINE / "tools" / "flow_referential.py", {"__future__", "re", "dataclasses", "datetime"})):
            for noeud in ast.walk(ast.parse(chemin.read_text(encoding="utf-8"))):
                if isinstance(noeud, ast.Import):
                    modules = [a.name for a in noeud.names]
                elif isinstance(noeud, ast.ImportFrom):
                    modules = [noeud.module or ""]
                else:
                    continue
                for module in modules:
                    self.assertIn(module.split(".")[0], permis, f"{chemin.name} ligne {noeud.lineno} : import hors liste : {module}")

    def test_aucun_lancement_ni_import_dynamique(self):
        for mot in ("subprocess", "importlib", "__import__"):
            self.assertNotIn(mot, self.source, mot)
        for noeud in ast.walk(self.arbre):
            if isinstance(noeud, ast.Call):
                f = noeud.func
                nom = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                self.assertNotIn(nom, {"__import__", "exec", "eval", "system", "popen"}, f"ligne {noeud.lineno}")

    def test_le_chargeur_n_importe_pas_le_module_de_tests_avec_effets_a_l_import(self):
        self.assertNotRegex(self.source, r"(?m)^\s*(import|from)\s+test_db\b")

    def test_l_aide_de_garde_n_a_aucun_effet_a_l_import(self):
        aide = ast.parse((RACINE / "tests" / "db" / "garde_base_jetable.py").read_text(encoding="utf-8"))
        for noeud in aide.body:
            if isinstance(noeud, ast.Expr) and isinstance(noeud.value, ast.Call):
                self.fail(f"appel au niveau du module, ligne {noeud.lineno}")
            if isinstance(noeud, ast.Assign) and isinstance(noeud.value, ast.Call):
                self.fail(f"appel au niveau du module, ligne {noeud.lineno}")


if __name__ == "__main__":
    unittest.main()
