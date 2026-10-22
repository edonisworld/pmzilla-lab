"""
Tests de la commande status de tools/db.py : contrôle des rôles de la liste, des rôles hors liste et de la version de pg_search
(change db-roles-status, design D5 et D6). Sans base : faux catalogue, fausses sessions, faux fichier compose, jamais de vraie connexion.

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sur base jetable (classe StatusBaseJetable) sont sautés sans elle ; l'auteur les lance par le script de base jetable.
"""
import contextlib
import io
import os
import re
import secrets
import stat
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import test_db as base          # noqa: E402
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

SECRET = "SecretDeStatus-ABC123_xyz"
COMPOSE = "name: x\nservices:\n  db:\n    image: paradedb/paradedb:0.26.2-pg18\n    restart: unless-stopped\n"
LISTE = db.ROLES_AVEC_MOT_DE_PASSE
HORS_LISTE = db.ROLES_SANS_MOT_DE_PASSE


class FauxCatalogue:
    """Connexion de superutilisateur : répond aux deux lectures du catalogue (rôles, extension)."""
    def __init__(self, roles=None, extension="0.26.2"):
        self.roles = roles if roles is not None else {}        # nom -> peut se connecter
        self.extension = extension
        self.requetes = []

    def execute(self, requete, params=None):
        texte = str(requete)
        self.requetes.append(texte)
        resultat = unittest.mock.MagicMock()
        if "pg_roles" in texte:
            resultat.fetchall.return_value = [(nom, peut) for nom, peut in self.roles.items() if nom in params[0]]
        elif "pg_extension" in texte:
            resultat.fetchone.return_value = None if self.extension is None else (self.extension,)
        else:
            raise AssertionError(f"lecture inattendue : {texte}")
        return resultat

    def close(self):
        pass


def connecteur(erreurs=None, appels=None):
    """Fausse fonction de connexion sous un rôle : lève l'erreur prévue pour ce rôle, sinon rend une session."""
    erreurs = erreurs or {}

    def connecter(*args, **kwargs):
        role = kwargs.get("role")
        if appels is not None:
            appels.append(kwargs)
        if role in erreurs:
            raise erreurs[role]
        return unittest.mock.MagicMock()
    return connecter


def par_role(etats):
    return {e.role: e for e in etats}


class EtatDesRoles(unittest.TestCase):
    def lancer(self, catalogue, mots_de_passe, erreurs=None):
        appels = []
        with unittest.mock.patch.object(db, "lire_mot_de_passe", lambda security=None, role=None: mots_de_passe.get(role)):
            etats = db.etat_des_roles(catalogue, connecter=connecteur(erreurs, appels))
        return par_role(etats), appels

    def test_ok(self):
        etats, appels = self.lancer(FauxCatalogue({"pmzilla_flow_views": True}), {"pmzilla_flow_views": SECRET})
        self.assertEqual((etats["pmzilla_flow_views"].niveau, etats["pmzilla_flow_views"].raison), ("ok", "ok"))
        self.assertEqual([a["role"] for a in appels], ["pmzilla_flow_views"])     # une seule session d'essai, sous ce rôle

    def test_non_configure_n_est_pas_un_probleme(self):
        etats, appels = self.lancer(FauxCatalogue({"pmzilla_cases": False}), {})
        self.assertEqual((etats["pmzilla_cases"].niveau, etats["pmzilla_cases"].raison), ("non_configure", "non_configure"))
        self.assertEqual(appels, [])

    def test_absent(self):
        etats, appels = self.lancer(FauxCatalogue({}), {"pmzilla_flow": SECRET})
        self.assertEqual((etats["pmzilla_flow"].niveau, etats["pmzilla_flow"].raison), ("probleme", "absent"))
        self.assertEqual(appels, [])

    def test_connexion_permise_sans_mot_de_passe_ne_tente_aucune_session(self):
        etats, appels = self.lancer(FauxCatalogue({"pmzilla_cases_ro": True}), {})
        self.assertEqual((etats["pmzilla_cases_ro"].niveau, etats["pmzilla_cases_ro"].raison), ("probleme", "sans_mot_de_passe"))
        self.assertEqual(appels, [])

    def test_mot_de_passe_trouve_mais_connexion_interdite(self):
        etats, appels = self.lancer(FauxCatalogue({"pmzilla_knowledge_ro": False}), {"pmzilla_knowledge_ro": SECRET})
        self.assertEqual((etats["pmzilla_knowledge_ro"].niveau, etats["pmzilla_knowledge_ro"].raison),
                         ("probleme", "connexion_interdite"))
        self.assertEqual(appels, [])

    def test_mot_de_passe_refuse(self):
        refus = db.ErreurBase("Connexion à la base impossible : password authentication failed.", mot_de_passe_refuse=True)
        etats, _ = self.lancer(FauxCatalogue({"pmzilla_flow_views": True}), {"pmzilla_flow_views": SECRET},
                               {"pmzilla_flow_views": refus})
        self.assertEqual((etats["pmzilla_flow_views"].niveau, etats["pmzilla_flow_views"].raison),
                         ("probleme", "mot_de_passe_refuse"))

    def test_autre_erreur_de_session_masquee(self):
        autre = db.ErreurBase(f"Connexion à la base impossible : serveur injoignable {SECRET}.")
        etats, _ = self.lancer(FauxCatalogue({"pmzilla_flow_views": True}), {"pmzilla_flow_views": SECRET},
                               {"pmzilla_flow_views": autre})
        etat = etats["pmzilla_flow_views"]
        self.assertEqual((etat.niveau, etat.raison), ("probleme", "connexion_impossible"))
        self.assertIn("serveur injoignable", etat.detail)
        self.assertNotIn(SECRET, etat.detail)

    def test_role_hors_liste_qui_peut_se_connecter_est_un_probleme_sans_session(self):
        catalogue = FauxCatalogue({"pmzilla_owner": False, "pmzilla_flow_ro": True, "pmzilla_quality": False})
        etats, appels = self.lancer(catalogue, {})
        self.assertEqual((etats["pmzilla_flow_ro"].niveau, etats["pmzilla_flow_ro"].raison), ("probleme", "connexion_permise"))
        self.assertNotIn("pmzilla_owner", etats)                   # sans connexion : aucune ligne
        self.assertNotIn("pmzilla_quality", etats)
        self.assertEqual(appels, [])

    def test_aucune_instruction_de_modification(self):
        catalogue = FauxCatalogue({"pmzilla_flow_views": True})
        self.lancer(catalogue, {"pmzilla_flow_views": SECRET})
        for requete in catalogue.requetes:
            self.assertRegex(requete.lstrip().upper(), r"^SELECT")

    def test_roles_hors_liste_et_liste_sont_disjoints(self):
        self.assertEqual(set(LISTE) & set(HORS_LISTE), set())
        self.assertIn("pmzilla_owner", HORS_LISTE)

    def test_les_deux_listes_couvrent_exactement_les_roles_crees_par_les_migrations(self):
        """Garde contre la dérive : un rôle ajouté par une migration doit entrer dans l'une des deux listes."""
        crees = set()
        for chemin in sorted(db.DOSSIER_MIGRATIONS.glob("*.sql")):
            texte = chemin.read_text(encoding="utf-8")
            crees |= set(re.findall(r"CREATE ROLE (pmzilla_\w+)", texte))
            for tableau in re.findall(r"ARRAY\[([^\]]*)\]\s*LOOP[^$]*?CREATE ROLE %I", texte):
                crees |= set(re.findall(r"'(pmzilla_\w+)'", tableau))
        self.assertIn("pmzilla_owner", crees)                       # l'analyse lit bien les boucles de création
        self.assertEqual(set(LISTE) | set(HORS_LISTE), crees)


class VersionAttendue(unittest.TestCase):
    def ecrire(self, texte):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        chemin = Path(dossier.name) / "docker-compose.yml"
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def test_tag_lu_sans_le_suffixe_postgresql(self):
        self.assertEqual(db.version_attendue_pg_search(self.ecrire(COMPOSE)), "0.26.2")

    def test_tag_sans_suffixe(self):
        self.assertEqual(db.version_attendue_pg_search(self.ecrire(COMPOSE.replace("0.26.2-pg18", "0.27.0"))), "0.27.0")

    def test_tag_illisible(self):
        for texte in (COMPOSE.replace("0.26.2-pg18", "latest"), COMPOSE.replace("paradedb/paradedb:0.26.2-pg18", "paradedb/paradedb"),
                      "services:\n  db:\n    restart: always\n"):
            with self.assertRaises(db.ErreurBase) as ctx:
                db.version_attendue_pg_search(self.ecrire(texte))
            self.assertIn("version attendue de pg_search illisible dans docker-compose.yml", str(ctx.exception))

    def test_fichier_absent(self):
        with self.assertRaises(db.ErreurBase):
            db.version_attendue_pg_search(Path("/inexistant/docker-compose.yml"))

    def test_le_fichier_du_depot_est_lisible(self):
        self.assertRegex(db.version_attendue_pg_search(db.FICHIER_COMPOSE), r"^\d+(\.\d+)+$")


class EtatPgSearch(unittest.TestCase):
    def test_ok(self):
        etat = db.etat_pg_search(FauxCatalogue(extension="0.26.2"), "0.26.2")
        self.assertEqual((etat.niveau, etat.raison, etat.installee), ("ok", "ok", "0.26.2"))

    def test_absente(self):
        etat = db.etat_pg_search(FauxCatalogue(extension=None), "0.26.2")
        self.assertEqual((etat.niveau, etat.raison), ("probleme", "absente"))

    def test_version_differente(self):
        etat = db.etat_pg_search(FauxCatalogue(extension="0.25.0"), "0.26.2")
        self.assertEqual((etat.niveau, etat.raison, etat.installee, etat.attendue), ("probleme", "version_differente", "0.25.0", "0.26.2"))


class CommandeStatus(unittest.TestCase):
    def lancer(self, roles=None, extension="0.26.2", mots_de_passe=None, erreurs=None, compose=COMPOSE, etat=None, tag=None):
        """Pilote main(["status"]) : faux catalogue, migrations simulées, Trousseau simulé. Rend (code, sortie, erreur)."""
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        chemin = Path(dossier.name) / "docker-compose.yml"
        chemin.write_text(compose, encoding="utf-8")
        catalogue = FauxCatalogue(roles if roles is not None else {r: False for r in LISTE}, extension)
        mots_de_passe = mots_de_passe or {}
        sessions = connecteur(erreurs)

        def connecter(*args, **kwargs):
            return sessions(*args, **kwargs) if kwargs.get("role") else catalogue
        etat_migrations = etat if etat is not None else db.Etat([], [])
        sortie, erreur = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(db, "connect", connecter), \
                unittest.mock.patch.object(db, "lister_migrations", return_value=[]), \
                unittest.mock.patch.object(db, "calculer_etat", return_value=etat_migrations) as calcul, \
                unittest.mock.patch.object(db, "lire_mot_de_passe", lambda security=None, role=None: mots_de_passe.get(role)), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = db.main(["status"], Path(dossier.name), compose=chemin)
        self.calcul = calcul
        return code, sortie.getvalue(), erreur.getvalue()

    def tous_ok(self):
        return ({r: True for r in LISTE}, {r: SECRET for r in LISTE})

    def test_rien_d_anormal_avec_migration_en_attente_et_roles_non_configures(self):
        en_attente = db.Etat([], [db.Migration(1, "0001_a.sql", Path("0001_a.sql"), "x")])
        code, sortie, erreur = self.lancer(etat=en_attente)
        self.assertEqual(code, 0)
        lignes = sortie.splitlines()
        self.assertEqual(lignes[0], "En attente : 0001_a.sql")
        for role in LISTE:
            self.assertIn(f"Rôle {role} : non configuré", lignes)
        self.assertIn("pg_search : ok (0.26.2)", lignes)
        self.assertEqual(lignes[-1], "État : aucun problème.")

    def test_roles_ok(self):
        roles, mots = self.tous_ok()
        code, sortie, _ = self.lancer(roles=roles, mots_de_passe=mots)
        self.assertEqual(code, 0)
        for role in LISTE:
            self.assertIn(f"Rôle {role} : ok", sortie.splitlines())

    def test_un_probleme_donne_le_code_3_et_le_resume_le_compte(self):
        roles, mots = self.tous_ok()
        mots.pop("pmzilla_cases")
        code, sortie, erreur = self.lancer(roles=roles, mots_de_passe=mots)
        self.assertEqual(code, 3)
        self.assertIn("Rôle pmzilla_cases : problème : connexion permise mais aucun mot de passe rangé "
                      "(Trousseau pmzilla-lab-db-pmzilla_cases, variable PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES)", sortie)
        self.assertEqual(sortie.splitlines()[-1], "État : 1 problème(s).")

    def test_mot_de_passe_refuse_propose_de_relancer_la_commande(self):
        roles, mots = self.tous_ok()
        refus = db.ErreurBase("password authentication failed", mot_de_passe_refuse=True)
        code, sortie, erreur = self.lancer(roles=roles, mots_de_passe=mots, erreurs={"pmzilla_flow_views": refus})
        self.assertEqual(code, 3)
        self.assertIn("Rôle pmzilla_flow_views : problème : mot de passe refusé par la base "
                      "(relancer : uv run tools/db.py role-password pmzilla_flow_views)", sortie)
        self.assertNotIn(SECRET, sortie + erreur)

    def test_autres_lignes_de_roles(self):
        roles = {"pmzilla_flow_views": False, "pmzilla_flow": False, "pmzilla_knowledge_ro": True, "pmzilla_flow_ro": True}
        roles.update({r: False for r in LISTE if r not in roles})
        del roles["pmzilla_cases"]
        code, sortie, _ = self.lancer(roles=roles, mots_de_passe={"pmzilla_flow": SECRET})
        self.assertEqual(code, 3)
        self.assertIn("Rôle pmzilla_cases : problème : absent de la base", sortie)
        self.assertIn("Rôle pmzilla_flow : problème : mot de passe rangé mais connexion interdite", sortie)
        self.assertIn("Rôle pmzilla_flow_ro : problème : connexion permise alors qu'il ne reçoit jamais de mot de passe", sortie)
        self.assertNotIn("Rôle pmzilla_owner", sortie)

    def test_autre_erreur_de_session(self):
        roles, mots = self.tous_ok()
        autre = db.ErreurBase(f"Connexion à la base impossible : coupure {SECRET}.")
        code, sortie, erreur = self.lancer(roles=roles, mots_de_passe=mots, erreurs={"pmzilla_cases_ro": autre})
        self.assertEqual(code, 3)
        self.assertIn("Rôle pmzilla_cases_ro : problème : connexion impossible : Connexion à la base impossible : coupure ***", sortie)
        self.assertNotIn(SECRET, sortie + erreur)

    def test_extension_differente_absente(self):
        code, sortie, _ = self.lancer(extension="0.25.0")
        self.assertEqual(code, 3)
        self.assertIn("pg_search : problème : version 0.25.0 installée, 0.26.2 attendue (image de la base)", sortie)
        code, sortie, _ = self.lancer(extension=None)
        self.assertEqual(code, 3)
        self.assertIn("pg_search : problème : extension absente", sortie)

    def test_tag_illisible_donne_le_code_1(self):
        code, sortie, erreur = self.lancer(compose=COMPOSE.replace("0.26.2-pg18", "latest"))
        self.assertEqual(code, 1)
        self.assertIn("Erreur : version attendue de pg_search illisible dans docker-compose.yml.", erreur)

    def test_migration_alteree_arrete_avant_les_nouveaux_controles(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        sortie, erreur = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(db, "connect", return_value=FauxCatalogue()), \
                unittest.mock.patch.object(db, "lister_migrations", return_value=[]), \
                unittest.mock.patch.object(db, "calculer_etat", side_effect=db.ErreurBase("Le fichier x a été modifié")), \
                unittest.mock.patch.object(db, "etat_des_roles") as roles, \
                unittest.mock.patch.object(db, "etat_pg_search") as extension, \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = db.main(["status"], Path(dossier.name))
        self.assertEqual(code, 1)
        self.assertIn("Erreur : Le fichier x a été modifié", erreur.getvalue())
        roles.assert_not_called()
        extension.assert_not_called()
        self.assertNotIn("Rôle", sortie.getvalue())

    def test_aucun_mot_de_passe_dans_les_sorties(self):
        roles, mots = self.tous_ok()
        code, sortie, erreur = self.lancer(roles=roles, mots_de_passe=mots)
        self.assertNotIn(SECRET, sortie + erreur)


FAUX_COFFRE_STATUT = """#!/bin/sh
# Faux Trousseau : rend le mot de passe stocké dans le fichier nommé par FAUX_COFFRE_<ROLE>, sinon échoue.
[ "$1" = "find-generic-password" ] || exit 2
role="${3#pmzilla-lab-db-}"
fichier="$FAUX_COFFRES/$role"
[ -s "$fichier" ] && cat "$fichier" && exit 0
exit 44
"""


class StatusBaseJetable(unittest.TestCase):
    """Tâche 2.4 : sur une base jetable seulement (sautée sans elle, lancée par l'auteur). Les rôles sont ceux de l'instance
    jetable : on y crée des rôles d'essai, présentés comme la liste autorisée par un patch."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn

    def test_roles_et_extension_sur_base_jetable(self):
        suffixe = secrets.token_hex(3)
        ok, refuse, jamais = (f"pmzilla_t_{n}_{suffixe}" for n in ("ok", "refuse", "jamais"))
        roles = (ok, refuse, jamais)

        def retirer():
            self._supprimer()
            with db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True) as nettoyage:
                for r in roles:
                    nettoyage.execute(f'DROP ROLE IF EXISTS "{r}"')
        self.addCleanup(retirer)
        for r in roles:
            self.admin.execute(f'CREATE ROLE "{r}" NOLOGIN')
            self.admin.execute(f'GRANT CONNECT ON DATABASE "{self.nom_base}" TO "{r}"')
        with tempfile.TemporaryDirectory() as dossier:
            dossier = Path(dossier)
            coffres = dossier / "coffres"
            coffres.mkdir()
            double = dossier / "security"
            double.write_text(FAUX_COFFRE_STATUT)
            double.chmod(double.stat().st_mode | stat.S_IXUSR)
            env = {db.VARIABLE_URL: self.url, db.VARIABLE_SECURITY: str(double), db.VARIABLE_MOT_DE_PASSE: base.MOT_DE_PASSE,
                   "FAUX_COFFRES": str(coffres)}
            with unittest.mock.patch.dict(os.environ, env), unittest.mock.patch.object(db, "ROLES_AVEC_MOT_DE_PASSE", roles):
                secret = db.generer_mot_de_passe()                 # posé comme le fait la commande, rangé dans le faux coffre
                c = self.conn()
                db.definir_mot_de_passe(c, ok, secret, roles)
                (coffres / ok).write_text(secret + "\n")
                autre = db.generer_mot_de_passe()                  # mot de passe différent dans le coffre : refusé
                c = self.conn()
                db.definir_mot_de_passe(c, refuse, db.generer_mot_de_passe(), roles)
                (coffres / refuse).write_text(autre + "\n")
                c = self.conn()
                etats = par_role(db.etat_des_roles(c, roles=roles, hors_liste=()))
                self.assertEqual(etats[ok].raison, "ok")
                self.assertEqual(etats[refuse].raison, "mot_de_passe_refuse")
                self.assertEqual(etats[jamais].raison, "non_configure")
        etat = db.etat_pg_search(c, db.version_attendue_pg_search(db.FICHIER_COMPOSE))     # image de la base jetable = celle du dépôt
        self.assertEqual((etat.niveau, etat.raison), ("ok", "ok"))


if __name__ == "__main__":
    unittest.main()
